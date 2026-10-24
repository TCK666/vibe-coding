"""分析任务引擎：状态机、8 类消息编排、取消、单会话单任务约束。

后台执行 run_task（独立 DB 会话），通过 ws_manager 向会话内所有连接广播；
断线不影响执行，历史可回放。
"""
import asyncio
import json
import re
import uuid
from datetime import datetime

from sqlalchemy import select, update

from ..core.errors import BizError
from ..db.session import SessionLocal
from ..llm import DeltaText, Finish, ToolCall, get_llm_client
from ..models import AnalysisResult, AnalysisTask, Conversation, Message, TaskLog
from . import message_service, tool_exec
from .ws_manager import ws_manager

MAX_TOOL_ROUNDS = 8
HISTORY_LIMIT = 20
FORCE_CANCEL_AFTER = 5.0  # 协作取消未生效的兜底秒数


class TaskCancelled(Exception):
    """协作式取消：由引擎在安全点主动抛出，避免 CancelledError 落在 DB 操作中间。"""


SYSTEM_PROMPT = (
    "你是经营归因分析助手。围绕用户的业务问题进行分析：需要数据时调用 db_query 工具查询业务表，"
    "基于证据给出归因结论。最终回答必须包含一个 ```json 代码块，字段为：\n"
    "problem_definition(问题定义), key_metrics(数组,每项含 metric_name/metric_value/metric_unit/metric_period), "
    "evidence_list(数组,每项含 source_type/source_name/evidence_text/related_metric/confidence), "
    "conclusion_text(归因结论), missing_data_text(待补充数据), next_action_text(下一步建议,至少2条)。\n"
    "JSON 之外用简洁的 markdown 说明归因过程。"
)

# 供测试注入的 LLM 工厂；生产即 get_llm_client
_llm_factory = get_llm_client

_running_tasks: dict[int, asyncio.Task] = {}
_cancel_requested: set[int] = set()


def _check_cancel(task_id: int) -> None:
    if task_id in _cancel_requested:
        raise TaskCancelled(f"任务 {task_id} 已被用户取消")


async def _broadcast(conversation_id: int, msg_type: str, data: dict) -> None:
    await ws_manager.broadcast(conversation_id, msg_type, data)


async def start_task(conversation_id: int, user_id: int, content: str) -> int:
    """创建分析任务（单会话单任务约束）并启动后台执行，返回 task_id。"""
    # 检查与插入分两个短会话：避免 SQLite 读事务升级写锁的瞬时 BUSY
    async with SessionLocal() as db:
        running = (
            await db.execute(
                select(AnalysisTask.id).where(
                    AnalysisTask.conversation_id == conversation_id,
                    AnalysisTask.task_status.in_(["queued", "running"]),
                )
            )
        ).scalars().first()
        if running:
            raise BizError("TASK_RUNNING", "该会话已有运行中的分析任务", 409)
    async with SessionLocal() as db:
        task = AnalysisTask(
            conversation_id=conversation_id,
            user_id=user_id,
            input_text=content,
            task_status="queued",
            current_step="排队中",
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

    tid = task.id
    _running_tasks[tid] = asyncio.create_task(run_task(tid, conversation_id, user_id, content))
    return tid


async def cancel_task(task_id: int, user_id: int) -> None:
    handle = _running_tasks.get(task_id)
    if handle is None:
        async with SessionLocal() as db:
            row = (
                await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))
            ).scalar_one_or_none()
        if row is None or row.user_id != user_id:
            raise BizError("TASK_NOT_FOUND", "任务不存在", 404)
        raise BizError("TASK_NOT_RUNNING", "任务已结束，无法取消", 400)
    # 协作式取消：引擎在安全点自行抛 TaskCancelled；兜底强杀防工具卡死
    _cancel_requested.add(task_id)
    asyncio.create_task(_force_cancel(task_id))


async def _force_cancel(task_id: int) -> None:
    await asyncio.sleep(FORCE_CANCEL_AFTER)
    handle = _running_tasks.get(task_id)
    if task_id in _cancel_requested and handle is not None and not handle.done():
        handle.cancel()


async def _set_task_status(
    task_id: int,
    conversation_id: int,
    status: str,
    step: str | None = None,
    started: bool = False,
    finished: bool = False,
    error: str | None = None,
) -> None:
    # 纯 UPDATE 直写：避免"读事务升级写锁"在 SQLite 上触发瞬时 BUSY
    values: dict = {"task_status": status}
    if step is not None:
        values["current_step"] = step
    if started:
        values["started_at"] = datetime.now()
    if finished:
        values["finished_at"] = datetime.now()
    if error is not None:
        values["error_message"] = error
    async with SessionLocal() as db:
        await db.execute(update(AnalysisTask).where(AnalysisTask.id == task_id).values(**values))
        await db.commit()
    await _broadcast(
        conversation_id,
        "task_status",
        {"task_id": task_id, "task_status": status, "current_step": step or ""},
    )


async def _add_log(task_id: int, level: str, log_type: str, content: str) -> None:
    async with SessionLocal() as db:
        db.add(TaskLog(task_id=task_id, log_level=level, log_type=log_type, log_content=content))
        await db.commit()


async def _build_context(conversation_id: int) -> list[dict]:
    """里程碑5简版上下文：system + 最近 HISTORY_LIMIT 条 user/assistant 消息。"""
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.seq_no.desc())
                .limit(HISTORY_LIMIT)
            )
        ).scalars().all()
    history = [
        {"role": m.role, "content": m.content or ""}
        for m in reversed(rows)
        if m.role in ("user", "assistant") and m.message_type in ("text", "result")
    ]
    return [{"role": "system", "content": SYSTEM_PROMPT}] + history


async def _stream_round(
    conversation_id: int, task_id: int, messages: list[dict], tools: list[dict] | None
) -> tuple[str, list[dict], str]:
    """跑一轮 LLM 流式：增量广播 message_delta，收集 tool_calls 分片。返回 (全文, 工具调用列表, finish_reason)。"""
    llm = _llm_factory()
    deltas: list[str] = []
    pending: dict[int, dict] = {}
    finish_reason = "stop"
    async for ev in llm.stream_chat(messages, tools):
        _check_cancel(task_id)
        if isinstance(ev, DeltaText):
            deltas.append(ev.text)
            await _broadcast(
                conversation_id, "message_delta", {"task_id": task_id, "delta_text": ev.text}
            )
        elif isinstance(ev, ToolCall):
            slot = pending.setdefault(
                ev.index, {"index": ev.index, "call_id": "", "name": "", "arguments": ""}
            )
            if ev.call_id:
                slot["call_id"] = ev.call_id
            if ev.name:
                slot["name"] = ev.name
            slot["arguments"] += ev.arguments
        elif isinstance(ev, Finish):
            finish_reason = ev.finish_reason
    calls = [
        {"call_id": c["call_id"] or f"call_{c['index']}", "name": c["name"], "arguments": c["arguments"]}
        for c in pending.values()
    ]
    return "".join(deltas), calls, finish_reason


def _extract_six_part(final_text: str) -> dict:
    match = re.search(r"```json\s*(\{.*?\})\s*```", final_text, re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(1))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


async def _persist_result(task_id: int, conversation_id: int, final_text: str) -> int:
    parsed = _extract_six_part(final_text)
    next_action = parsed.get("next_action_text")
    if isinstance(next_action, list):
        next_action = json.dumps(next_action, ensure_ascii=False)
    async with SessionLocal() as db:
        result = AnalysisResult(
            task_id=task_id,
            conversation_id=conversation_id,
            problem_definition=parsed.get("problem_definition"),
            key_metrics_json=parsed.get("key_metrics"),
            evidence_list_json=parsed.get("evidence_list"),
            conclusion_text=parsed.get("conclusion_text"),
            missing_data_text=parsed.get("missing_data_text"),
            next_action_text=next_action,
            result_markdown=final_text,
        )
        db.add(result)
        await db.commit()
        await db.refresh(result)
        return result.id


async def run_task(task_id: int, conversation_id: int, user_id: int, content: str) -> None:
    try:
        _check_cancel(task_id)
        await _broadcast(
            conversation_id,
            "message_start",
            {"task_id": task_id, "conversation_id": conversation_id},
        )
        _check_cancel(task_id)
        await _set_task_status(task_id, conversation_id, "running", "准备分析上下文", started=True)
        await _add_log(task_id, "INFO", "state_change", f"任务开始: {content[:100]}")
        _check_cancel(task_id)

        async with SessionLocal() as db:
            await message_service.append_message(
                db, conversation_id, role="user", content=content
            )
        _check_cancel(task_id)
        messages = await _build_context(conversation_id)
        tools = tool_exec.TOOL_SCHEMAS

        for round_no in range(MAX_TOOL_ROUNDS):
            _check_cancel(task_id)
            final_text, calls, finish_reason = await _stream_round(
                conversation_id, task_id, messages, tools
            )
            if finish_reason != "tool_calls" or not calls:
                break

            _check_cancel(task_id)
            await _set_task_status(
                task_id, conversation_id, "running", f"执行工具({round_no + 1}轮:{len(calls)}个)"
            )
            messages.append({"role": "assistant", "content": final_text or None, "tool_calls": [
                {"id": c["call_id"], "type": "function",
                 "function": {"name": c["name"], "arguments": c["arguments"]}}
                for c in calls
            ]})
            for c in calls:
                _check_cancel(task_id)
                await _broadcast(
                    conversation_id,
                    "tool_start",
                    {"task_id": task_id, "tool_name": c["name"]},
                )
                try:
                    summary, full_output = await tool_exec.execute_tool(c["name"], c["arguments"])
                    tool_status = "success"
                except Exception as e:  # 工具失败把错误作为结果回传 LLM，继续对话
                    summary, full_output, tool_status = f"工具执行失败: {e}", f"error: {e}", "failed"
                await _broadcast(
                    conversation_id,
                    "tool_finish",
                    {"task_id": task_id, "tool_name": c["name"], "tool_result_summary": summary},
                )
                await _add_log(task_id, "INFO" if tool_status == "success" else "WARNING",
                               "tool_exec", f"{c['name']} args={c['arguments'][:200]} => {summary}")
                async with SessionLocal() as db:
                    await message_service.append_message(
                        db, conversation_id, role="tool", message_type="tool_event",
                        content=summary, tool_name=c["name"], tool_status=tool_status,
                    )
                messages.append({"role": "tool", "tool_call_id": c["call_id"], "content": full_output})
        else:
            final_text = final_text + "\n\n(已达工具调用轮次上限，基于现有证据给出结论)"

        _check_cancel(task_id)
        result_id = await _persist_result(task_id, conversation_id, final_text)
        async with SessionLocal() as db:
            await message_service.append_message(
                db, conversation_id, role="assistant", message_type="result", content=final_text
            )
        await _broadcast(conversation_id, "result_ready", {"task_id": task_id, "result_id": result_id})
        await _set_task_status(task_id, conversation_id, "success", "分析完成", finished=True)
        await _broadcast(
            conversation_id,
            "done",
            {"task_id": task_id, "finished_at": datetime.now().isoformat(timespec="seconds")},
        )
    except TaskCancelled as e:
        await _set_task_status(task_id, conversation_id, "cancelled", "已取消", finished=True)
        await _add_log(task_id, "WARNING", "cancel", str(e))
        await _broadcast(
            conversation_id,
            "done",
            {"task_id": task_id, "finished_at": datetime.now().isoformat(timespec="seconds")},
        )
    except asyncio.CancelledError:
        # 强杀兜底路径（协作取消超时）：尽量收尾，不再向上抛
        try:
            await _set_task_status(task_id, conversation_id, "cancelled", "已取消", finished=True)
            await _broadcast(
                conversation_id,
                "done",
                {"task_id": task_id, "finished_at": datetime.now().isoformat(timespec="seconds")},
            )
        except Exception:
            pass
    except Exception as e:
        await _set_task_status(
            task_id, conversation_id, "failed", "分析失败", finished=True, error=str(e)
        )
        await _add_log(task_id, "ERROR", "error", str(e))
        await _broadcast(conversation_id, "error", {"task_id": task_id, "error_message": str(e)})
        await _broadcast(
            conversation_id,
            "done",
            {"task_id": task_id, "finished_at": datetime.now().isoformat(timespec="seconds")},
        )
    finally:
        _running_tasks.pop(task_id, None)
        _cancel_requested.discard(task_id)


def new_request_id() -> str:
    return uuid.uuid4().hex
