"""里程碑6 验收：结果校验与导出 / 文件与命令工具 / 附件解析 / 上下文压缩。"""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.llm import DeltaText, Finish, ToolCall
from app.main import app
from app.services import task_engine
from app.services.tool_exec import ToolContext, execute_tool
from app.schemas.result import validate_six_part

ALICE = {"sub": "u-alice", "username": "alice", "display_name": "分析用户A", "role": "user"}

VALID_SIX = {
    "problem_definition": "近30天转化率为何下降？",
    "key_metrics": [
        {"metric_name": "下单转化率", "metric_value": 3.2, "metric_unit": "%", "metric_period": "近30天"}
    ],
    "evidence_list": [
        {"source_type": "db_query", "source_name": "biz_order", "evidence_text": "转化率下降",
         "related_metric": "下单转化率", "confidence": 0.9}
    ],
    "conclusion_text": "测试结论：详情页改版导致下降。",
    "missing_data_text": "缺少热力图数据。",
    "next_action_text": ["回滚改版观察一周", "分渠道留存对比验证"],
}


def _setup():
    async def run():
        from app.db.session import SessionLocal, init_db
        from app.services.user_service import upsert_from_userinfo

        await init_db()
        async with SessionLocal() as db:
            alice = await upsert_from_userinfo(db, ALICE)
            bob = await upsert_from_userinfo(db, {"sub": "u-bob", "username": "bob", "display_name": "B", "role": "user"})
        return alice.id, bob.id

    return asyncio.run(run())


ALICE_ID, BOB_ID = _setup()


def _auth():
    token, _ = create_access_token(ALICE_ID, f"u-{ALICE_ID}", "user")
    return {"Authorization": f"Bearer {token}"}


def _auth_bob():
    token, _ = create_access_token(BOB_ID, f"u-{BOB_ID}", "user")
    return {"Authorization": f"Bearer {token}"}


class FakeLLM:
    """首轮工具调用，带 tool 结果后输出六部分 JSON；记录收到的上下文。"""

    def __init__(self, final_text: str):
        self.final_text = final_text
        self.seen_contexts: list[list[dict]] = []

    async def chat(self, messages):
        return "测试摘要：用户追问了转化率问题。"

    async def stream_chat(self, messages, tools=None):
        has_tool = any(m.get("role") == "tool" for m in messages)
        if has_tool:
            self.seen_contexts.append([dict(m) for m in messages])
            for piece in (self.final_text[:20], self.final_text[20:]):
                yield DeltaText(piece)
            yield Finish("stop")
        elif tools:
            yield ToolCall(index=0, call_id="c1", name="db_query", arguments='{"sql":"SELECT 1"}')
            yield Finish("tool_calls")
        else:
            yield DeltaText(self.final_text)
            yield Finish("stop")


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _run_round(client, cid, fake):
    task_engine._llm_factory = lambda: fake
    token = client.post("/api/chat/ws-token", json={"conversation_id": cid}, headers=_auth()).json()["data"]["websocket_token"]
    with client.websocket_connect(f"/api/chat/ws/chat?websocket_token={token}&conversation_id={cid}") as ws:
        ws.send_json({"type": "chat", "content": "分析测试"})
        events = []
        while True:
            ev = ws.receive_json()
            events.append(ev)
            if ev["type"] == "done":
                return events


def _new_conv(client):
    return client.post("/api/chat/create", json={"title": "m6"}, headers=_auth()).json()["data"]["conversation_id"]


def test_six_part_validation():
    ok = validate_six_part(VALID_SIX)
    assert ok.key_metrics[0].metric_name == "下单转化率"
    with pytest.raises(Exception):
        validate_six_part({**VALID_SIX, "next_action_text": ["只有一条"]})
    with pytest.raises(Exception):
        validate_six_part({**VALID_SIX, "evidence_list": [{**VALID_SIX["evidence_list"][0], "confidence": 1.5}]})


def test_result_flow_with_export_and_download(client):
    final = "归因过程如下。\n```json\n" + json.dumps(VALID_SIX, ensure_ascii=False) + "\n```"
    cid = _new_conv(client)
    events = _run_round(client, cid, FakeLLM(final))
    task_id = events[0]["data"]["task_id"]
    result_id = next(e for e in events if e["type"] == "result_ready")["data"]["result_id"]

    r = client.get(f"/api/results/{task_id}", headers=_auth())
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["problem_definition"] == VALID_SIX["problem_definition"]
    assert data["key_metrics"][0]["metric_name"] == "下单转化率"
    assert len(json.loads(data["next_action_text"])) == 2
    assert "# 经营归因分析报告" in data["result_markdown"]
    assert data["result_file_path"] == f"exports/{ALICE_ID}/{cid}/{task_id}.md"

    # 导出文件下载且内容一致
    d = client.get(f"/api/results/{task_id}/download", headers=_auth())
    assert d.status_code == 200
    assert d.content.decode("utf-8") == data["result_markdown"]

    # 会话最新结果
    r = client.get(f"/api/results/latest/{cid}", headers=_auth())
    assert r.json()["data"]["result"]["result_id"] == result_id
    # 非本人 → 404
    assert client.get(f"/api/results/{task_id}", headers=_auth_bob()).status_code == 404


def test_validation_failure_fallback(client):
    bad = {**VALID_SIX, "next_action_text": ["只有一条建议"]}
    final = "```json\n" + json.dumps(bad, ensure_ascii=False) + "\n```"
    cid = _new_conv(client)
    events = _run_round(client, cid, FakeLLM(final))
    task_id = events[0]["data"]["task_id"]
    r = client.get(f"/api/results/{task_id}", headers=_auth())
    data = r.json()["data"]
    assert data["result_markdown"] == final  # 原始文本兜底
    assert data["result_file_path"] is None  # 校验失败不导出


def test_file_and_cmd_tools():
    ctx = ToolContext(user_id=ALICE_ID, conversation_id=900001)

    async def run():
        s1, f1 = await execute_tool("file_write", '{"path":"mid/stats.txt","content":"hello 归因"}', ctx)
        s2, f2 = await execute_tool("file_read", '{"path":"mid/stats.txt"}', ctx)
        return (s1, f1), (s2, f2)

    (s1, f1), (s2, f2) = asyncio.run(run())
    assert "成功" in s1 and "8 字符" in s1  # len("hello 归因") = 8（汉字按 1 字符计）
    assert f2 == "hello 归因"

    async def bad_path():
        await execute_tool("file_read", '{"path":"../../secrets"}', ctx)

    with pytest.raises(Exception) as ei:
        asyncio.run(bad_path())
    assert ei.value.code == "FILE_PATH_INVALID"


def test_text_search_tool():
    ctx = ToolContext(user_id=ALICE_ID, conversation_id=900002)

    async def run():
        await execute_tool("file_write", '{"path":"notes.txt","content":"line1: 转化率下降\\nline2: 正常"}', ctx)
        return await execute_tool("text_search", '{"keyword":"转化率"}', ctx)

    summary, full = asyncio.run(run())
    assert "命中 1 条" in summary
    assert "notes.txt:1" in full and "转化率下降" in full


def test_cmd_exec_whitelist_and_run():
    ctx = ToolContext(user_id=ALICE_ID, conversation_id=900003)

    async def run():
        return await execute_tool("cmd_exec", '{"command":"python -c \\"print(42)\\""}', ctx)

    summary, full = asyncio.run(run())
    assert "成功" in summary and "42" in full

    async def forbidden():
        await execute_tool("cmd_exec", '{"command":"del /q something"}', ctx)

    with pytest.raises(Exception) as ei:
        asyncio.run(forbidden())
    assert ei.value.code == "TOOL_CMD_FORBIDDEN"


def test_attachment_parse_and_context_injection(client):
    cid = _new_conv(client)
    up = client.post(
        "/api/attachment/upload",
        data={"conversation_id": str(cid)},
        files={"file": ("销售数据.txt", "渠道A转化率 8.1% -> 3.2%".encode("utf-8"), "text/plain")},
        headers=_auth(),
    )
    assert up.json()["data"]["parse_status"] == "success"
    # 二进制文件 → failed
    up2 = client.post(
        "/api/attachment/upload",
        data={"conversation_id": str(cid)},
        files={"file": ("图.png", b"\x89PNG\r\n\x1a\nxxxx", "image/png")},
        headers=_auth(),
    )
    assert up2.json()["data"]["parse_status"] == "failed"

    fake = FakeLLM("好\n```json\n" + json.dumps(VALID_SIX, ensure_ascii=False) + "\n```")
    _run_round(client, cid, fake)
    # system 上下文应注入附件解析文本
    assert fake.seen_contexts, "未捕获到 LLM 上下文"
    system_text = fake.seen_contexts[0][0]["content"]
    assert "《销售数据.txt》" in system_text
    assert "渠道A转化率" in system_text


def test_context_compression_creates_summary(client):
    cid = _new_conv(client)

    async def seed():
        from app.db.session import SessionLocal
        from app.services.message_service import append_message

        async with SessionLocal() as db:
            for i in range(6):
                await append_message(db, cid, role="user" if i % 2 == 0 else "assistant",
                                     content=f"历史消息{i}" + "x" * 1800)

    asyncio.run(seed())
    fake = FakeLLM("结论\n```json\n" + json.dumps(VALID_SIX, ensure_ascii=False) + "\n```")
    _run_round(client, cid, fake)

    async def count_summaries():
        from sqlalchemy import func, select

        from app.db.session import SessionLocal
        from app.models import ContextSummary

        async with SessionLocal() as db:
            return (
                await db.execute(
                    select(func.count()).select_from(ContextSummary)
                    .where(ContextSummary.conversation_id == cid)
                )
            ).scalar_one()

    assert asyncio.run(count_summaries()) == 1
    # 摘要注入到 system
    assert any("历史对话摘要" in c[0]["content"] for c in fake.seen_contexts)
