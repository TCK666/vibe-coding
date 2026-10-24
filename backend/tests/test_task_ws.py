"""里程碑5 验收：ws-token 一次性鉴权 / 8类消息全流程 / 取消 / 单会话单任务 / 任务查询。"""
import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.llm import DeltaText, Finish, ToolCall
from app.main import app
from app.services import task_engine

ALICE = {"sub": "u-alice", "username": "alice", "display_name": "分析用户A", "role": "user"}


def _setup():
    async def run():
        from app.db.session import SessionLocal, init_db
        from app.services.user_service import upsert_from_userinfo

        await init_db()
        async with SessionLocal() as db:
            alice = await upsert_from_userinfo(db, ALICE)
        return alice.id

    return asyncio.run(run())


ALICE_ID = _setup()


def _auth():
    token, _ = create_access_token(ALICE_ID, f"u-{ALICE_ID}", "user")
    return {"Authorization": f"Bearer {token}"}


class FakeLLM:
    """按 mock_llm 剧本规则产出事件：首轮工具调用，带 tool 结果后流式输出。"""

    def __init__(self, delay=0.0, n_deltas=3):
        self.delay = delay
        self.n_deltas = n_deltas

    async def stream_chat(self, messages, tools=None):
        has_tool_result = any(m.get("role") == "tool" for m in messages)
        if tools and not has_tool_result:
            yield ToolCall(index=0, call_id="call_1", name="db_query", arguments='{"sql": ')
            yield ToolCall(index=0, call_id="", name="", arguments='"SELECT 1"}')
            yield Finish("tool_calls")
        else:
            for i in range(self.n_deltas):
                if self.delay:
                    await asyncio.sleep(self.delay)
                yield DeltaText(f"piece{i}.")


class Receiver:
    """带超时的 WS 收包（daemon 线程实现，超时/失败都不会卡住解释器退出）。"""

    def __init__(self, ws):
        self.ws = ws

    def recv(self, timeout=20):
        import threading

        result: dict = {}

        def run():
            try:
                result["value"] = self.ws.receive_json()
            except BaseException as e:  # noqa: BLE001  线程内兜底
                result["error"] = e

        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(timeout)
        if "error" in result:
            raise result["error"]
        if "value" not in result:
            raise TimeoutError(f"ws receive timeout after {timeout}s")
        return result["value"]

    def collect_until_done(self, timeout=30):
        events = []
        while True:
            ev = self.recv(timeout=timeout)
            events.append(ev)
            if ev["type"] == "done":
                return events


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _new_conversation(client):
    r = client.post("/api/chat/create", json={"title": "ws测试"}, headers=_auth())
    return r.json()["data"]["conversation_id"]


def _ws_url(token, cid):
    return f"/api/chat/ws/chat?websocket_token={token}&conversation_id={cid}"


def test_ws_token_issue(client):
    cid = _new_conversation(client)
    r = client.post("/api/chat/ws-token", json={"conversation_id": cid}, headers=_auth())
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["websocket_token"] and data["expires_in"] == 30


def test_ws_rejects_bad_token(client):
    with pytest.raises(WebSocketDisconnect) as ei:
        with client.websocket_connect(_ws_url("not-a-real-token", 1)) as ws:
            ws.receive_json()
    assert ei.value.code == 4401


def test_ws_rejects_reused_token(client):
    """复用拒绝走 _consume_ws_token 单测（TestClient 每个 WS 会话独立事件循环，
    两次 websocket_connect 的跨循环连接创建会被 anyio 取消，属测试工具限制）。"""
    from datetime import datetime, timedelta

    from app.api.ws import _consume_ws_token

    async def run():
        from app.db.session import SessionLocal
        from app.models import WebsocketToken

        async with SessionLocal() as db:
            tok = WebsocketToken(
                user_id=ALICE_ID, conversation_id=999, token="unit-tok-1",
                expires_at=datetime.now() + timedelta(seconds=30),
            )
            db.add(tok)
            expired = WebsocketToken(
                user_id=ALICE_ID, conversation_id=999, token="unit-tok-2",
                expires_at=datetime.now() - timedelta(seconds=1),
            )
            db.add(expired)
            await db.commit()

        # 首次消费：合法
        assert await _consume_ws_token(SessionLocal(), "unit-tok-1", 999) == ALICE_ID
        # 复用：None
        assert await _consume_ws_token(SessionLocal(), "unit-tok-1", 999) is None
        # conversation_id 不匹配：None
        assert await _consume_ws_token(SessionLocal(), "unit-tok-1", 998) is None
        # 过期：None
        assert await _consume_ws_token(SessionLocal(), "unit-tok-2", 999) is None
        # 不存在：None
        assert await _consume_ws_token(SessionLocal(), "nope", 999) is None

    asyncio.run(run())


def test_full_round_emits_all_8_message_types(client, monkeypatch):
    monkeypatch.setattr(task_engine, "_llm_factory", lambda: FakeLLM())
    cid = _new_conversation(client)
    token = client.post("/api/chat/ws-token", json={"conversation_id": cid}, headers=_auth()).json()["data"]["websocket_token"]

    with client.websocket_connect(_ws_url(token, cid)) as ws:
        ws.send_json({"type": "chat", "content": "近30天转化率如何"})
        events = Receiver(ws).collect_until_done()

    types = [e["type"] for e in events]
    assert set(types) == {
        "message_start", "message_delta", "tool_start", "tool_finish",
        "task_status", "result_ready", "error", "done",
    } - {"error"} | {"done"}  # 正常流程无 error
    assert "error" not in types
    assert types[-1] == "done"
    assert types[0] == "message_start"

    start = events[0]["data"]
    assert start["conversation_id"] == cid and start["task_id"] > 0
    # delta 分片到达
    assert sum(1 for t in types if t == "message_delta") >= 3
    # 工具事件字段
    tool_finish = next(e for e in events if e["type"] == "tool_finish")
    assert tool_finish["data"]["tool_name"] == "db_query"
    assert "tool_result_summary" in tool_finish["data"]
    # 结果与任务行落库
    task_id = start["task_id"]
    result_ready = next(e for e in events if e["type"] == "result_ready")["data"]
    assert result_ready["result_id"] > 0

    async def check_rows():
        from sqlalchemy import select

        from app.db.session import SessionLocal
        from app.models import AnalysisResult, AnalysisTask, Message

        async with SessionLocal() as db:
            task = (await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))).scalar_one()
            result = (await db.execute(select(AnalysisResult).where(AnalysisResult.task_id == task_id))).scalar_one()
            tool_msgs = (await db.execute(
                select(Message).where(Message.conversation_id == cid, Message.message_type == "tool_event")
            )).scalars().all()
        return task, result, tool_msgs

    task, result, tool_msgs = asyncio.run(check_rows())
    assert task.task_status == "success" and task.started_at and task.finished_at
    assert result.result_markdown
    assert len(tool_msgs) == 1 and tool_msgs[0].tool_name == "db_query"


def test_single_running_task_constraint(client, monkeypatch):
    monkeypatch.setattr(task_engine, "_llm_factory", lambda: FakeLLM(delay=0.08, n_deltas=25))
    cid = _new_conversation(client)
    token = client.post("/api/chat/ws-token", json={"conversation_id": cid}, headers=_auth()).json()["data"]["websocket_token"]

    with client.websocket_connect(_ws_url(token, cid)) as ws:
        ws.send_json({"type": "chat", "content": "第一个问题"})
        recv = Receiver(ws)
        start = recv.recv()
        assert start["type"] == "message_start"
        task1 = start["data"]["task_id"]
        ws.send_json({"type": "chat", "content": "第二个问题"})
        # 第二条被拒：error(TASK_RUNNING) 会与任务1的事件流交错，扫描直到找到
        rejected = None
        for _ in range(60):
            ev = recv.recv()
            if ev["type"] == "error" and "TASK_RUNNING" in ev["data"]["error_message"]:
                rejected = ev
                break
            assert ev["type"] != "done", "任务1提前结束，未触发并发约束"
        assert rejected is not None, "未收到 TASK_RUNNING 拒绝"
        events = recv.collect_until_done()
    assert events[-1]["data"]["task_id"] == task1  # 原任务正常收尾


def test_cancel_running_task(client, monkeypatch):
    monkeypatch.setattr(task_engine, "_llm_factory", lambda: FakeLLM(delay=0.05, n_deltas=80))
    cid = _new_conversation(client)
    token = client.post("/api/chat/ws-token", json={"conversation_id": cid}, headers=_auth()).json()["data"]["websocket_token"]

    with client.websocket_connect(_ws_url(token, cid)) as ws:
        ws.send_json({"type": "chat", "content": "会被取消的问题"})
        recv = Receiver(ws)
        start = recv.recv()
        task_id = start["data"]["task_id"]
        # 等到进入 running 再取消
        while True:
            ev = recv.recv()
            if ev["type"] == "task_status" and ev["data"]["task_status"] == "running":
                break
        ws.send_json({"type": "cancel", "task_id": task_id})
        events = recv.collect_until_done()
    statuses = [e["data"]["task_status"] for e in events if e["type"] == "task_status"]
    assert "cancelled" in statuses
    assert events[-1]["type"] == "done"

    async def check_row():
        from sqlalchemy import select

        from app.db.session import SessionLocal
        from app.models import AnalysisTask

        async with SessionLocal() as db:
            return (await db.execute(select(AnalysisTask).where(AnalysisTask.id == task_id))).scalar_one()

    task = asyncio.run(check_row())
    assert task.task_status == "cancelled" and task.finished_at


def test_get_task_endpoint(client, monkeypatch):
    monkeypatch.setattr(task_engine, "_llm_factory", lambda: FakeLLM())
    cid = _new_conversation(client)
    token = client.post("/api/chat/ws-token", json={"conversation_id": cid}, headers=_auth()).json()["data"]["websocket_token"]
    with client.websocket_connect(_ws_url(token, cid)) as ws:
        ws.send_json({"type": "chat", "content": "查询任务接口测试"})
        task_id = Receiver(ws).recv()["data"]["task_id"]
        Receiver(ws).collect_until_done()

    r = client.get(f"/api/tasks/{task_id}", headers=_auth())
    assert r.status_code == 200
    data = r.json()["data"]
    for field in ("task_status", "current_step", "started_at", "finished_at", "error_message"):
        assert field in data
    assert data["task_status"] == "success"
    # 不存在/非本人 → 404
    assert client.get("/api/tasks/999999", headers=_auth()).status_code == 404
    assert client.get(f"/api/tasks/{task_id}").status_code == 401
