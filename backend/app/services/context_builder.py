"""上下文拼装：system + 摘要段 + 未摘要历史 + 附件解析文本；超阈值触发压缩。"""
from sqlalchemy import select

from ..db.session import SessionLocal
from ..models import Attachment, ContextSummary, Conversation, Message, SystemConfig
from .tool_exec import ToolContext

DEFAULT_CONTEXT_THRESHOLD = 8000
PER_ATTACHMENT_LIMIT = 3000


async def _get_threshold() -> int:
    try:
        async with SessionLocal() as db:
            row = (
                await db.execute(
                    select(SystemConfig.config_value).where(
                        SystemConfig.config_key == "analysis.context_threshold"
                    )
                )
            ).scalar()
        return int(row) if row else DEFAULT_CONTEXT_THRESHOLD
    except Exception:
        return DEFAULT_CONTEXT_THRESHOLD


def _render_message(m: Message) -> str:
    if m.message_type == "tool_event":
        return f"[工具] {m.tool_name}: {(m.content or '')[:200]}"
    prefix = "用户" if m.role == "user" else "助手"
    return f"{prefix}: {m.content or ''}"


async def build_context(conversation_id: int, llm) -> tuple[list[dict], ToolContext]:
    """构建 LLM 消息列表；必要时压缩旧历史。返回 (messages, tool_ctx)。"""
    threshold = await _get_threshold()
    async with SessionLocal() as db:
        conv = (
            await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        ).scalar_one()
        user_id = conv.user_id
        atts = (
            await db.execute(
                select(Attachment).where(
                    Attachment.conversation_id == conversation_id,
                    Attachment.parse_status == "success",
                )
            )
        ).scalars().all()
        summaries = (
            await db.execute(
                select(ContextSummary)
                .where(ContextSummary.conversation_id == conversation_id)
                .order_by(ContextSummary.end_seq_no)
            )
        ).scalars().all()
        last_end = summaries[-1].end_seq_no if summaries else 0
        msgs = (
            await db.execute(
                select(Message)
                .where(Message.conversation_id == conversation_id, Message.seq_no > last_end)
                .order_by(Message.seq_no)
            )
        ).scalars().all()

        # 压缩：未摘要消息超阈值且足够多 → 旧一半交给 LLM 摘要
        total_chars = sum(len(_render_message(m)) for m in msgs)
        if total_chars > threshold and len(msgs) > 4:
            cut = len(msgs) // 2
            older, newer = list(msgs[:cut]), list(msgs[cut:])
            older_text = "\n".join(_render_message(m) for m in older)
            summary_text = await _summarize(llm, older_text)
            new_row = ContextSummary(
                conversation_id=conversation_id,
                start_seq_no=older[0].seq_no,
                end_seq_no=older[-1].seq_no,
                summary_text=summary_text,
            )
            db.add(new_row)
            await db.commit()
            await db.refresh(new_row)
            msgs = newer
            summaries = list(summaries) + [new_row]

    ctx = ToolContext(user_id=user_id, conversation_id=conversation_id)

    parts: list[str] = []
    if summaries:
        seg = "; ".join(
            f"【摘要 seq{s.start_seq_no}-{s.end_seq_no}】{s.summary_text}" for s in summaries
        )
        parts.append(f"历史对话摘要:\n{seg}")

    att_blocks = []
    from pathlib import Path

    from ..tools import _paths

    for a in atts:
        pf = _paths.WORKSPACE_ROOT / str(user_id) / str(conversation_id) / f"parsed_{a.id}.txt"
        if pf.is_file():
            text = pf.read_text(encoding="utf-8", errors="replace")[:PER_ATTACHMENT_LIMIT]
            att_blocks.append(f"--- 附件《{a.file_name}》解析文本(截断) ---\n{text}")

    system = (
        "你是经营归因分析助手。围绕用户的业务问题持续分析：需要数据时调用工具查询/检索，"
        "基于证据给出归因结论。最终回答必须包含一个 ```json 代码块，字段为：\n"
        "problem_definition(问题定义), key_metrics(数组,每项含 metric_name/metric_value/metric_unit/metric_period), "
        "evidence_list(数组,每项含 source_type/source_name/evidence_text/related_metric/confidence), "
        "conclusion_text(归因结论), missing_data_text(待补充数据), next_action_text(下一步建议,至少2条)。\n"
        "JSON 之外用简洁的 markdown 说明归因过程。当前会话: " + conv.title + "。"
    )
    if att_blocks:
        system += "\n\n可用附件解析文本:\n" + "\n".join(att_blocks)
    if parts:
        system += "\n\n" + parts[0]

    messages = [{"role": "system", "content": system}] + [
        {"role": m.role, "content": m.content or ""}
        for m in msgs
        if m.role in ("user", "assistant") and m.message_type in ("text", "result")
    ]
    return messages, ctx


async def _summarize(llm, older_text: str) -> str:
    prompt = (
        "请把以下经营分析对话历史压缩成不超过 400 字的要点摘要，"
        "保留问题、关键数据、已得出的结论和未完成事项：\n\n" + older_text[:6000]
    )
    try:
        return (await llm.chat([{"role": "user", "content": prompt}]))[:600]
    except Exception:
        return "(摘要生成失败，仅保留要点) " + older_text[:300]
