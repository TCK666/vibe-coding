"""里程碑4 验收：会话CRUD / seq_no / 附件上传下载 / 跨用户隔离 / 级联删除 / 路径校验。"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app

ALICE = {"sub": "u-alice", "username": "alice", "display_name": "分析用户A", "role": "user"}
BOB = {"sub": "u-bob", "username": "bob", "display_name": "分析用户B", "role": "user"}


def _setup():
    async def run():
        from app.db.session import SessionLocal, init_db
        from app.services.user_service import upsert_from_userinfo

        await init_db()
        async with SessionLocal() as db:
            alice = await upsert_from_userinfo(db, ALICE)
            bob = await upsert_from_userinfo(db, BOB)
        return alice.id, bob.id

    return asyncio.run(run())


ALICE_ID, BOB_ID = _setup()


def _auth(user_id: int) -> dict[str, str]:
    token, _ = create_access_token(user_id, f"u-{user_id}", "user")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_conversation_crud(client):
    r = client.post("/api/chat/create", json={"title": "转化率分析"}, headers=_auth(ALICE_ID))
    assert r.status_code == 200
    data = r.json()["data"]
    cid = data["conversation_id"]
    assert data["status"] == "active"

    r = client.get("/api/chat/ls", headers=_auth(ALICE_ID))
    titles = [c["title"] for c in r.json()["data"]["conversations"]]
    assert "转化率分析" in titles

    r = client.post(
        "/api/chat/update",
        json={"conversation_id": cid, "title": "转化率下降归因"},
        headers=_auth(ALICE_ID),
    )
    assert r.json()["data"]["title"] == "转化率下降归因"

    r = client.get(f"/api/chat/ls/{cid}", headers=_auth(ALICE_ID))
    assert r.json()["data"]["messages"] == []


def test_message_seq_no_ordered(client):
    async def append(cid):
        from app.db.session import SessionLocal
        from app.services.message_service import append_message

        async with SessionLocal() as db:
            for i in range(3):
                await append_message(db, cid, role="user", content=f"问题{i}")

    r = client.post("/api/chat/create", json={"title": "seq测试"}, headers=_auth(ALICE_ID))
    cid = r.json()["data"]["conversation_id"]
    asyncio.run(append(cid))

    r = client.get(f"/api/chat/ls/{cid}", headers=_auth(ALICE_ID))
    msgs = r.json()["data"]["messages"]
    assert [m["seq_no"] for m in msgs] == [1, 2, 3]
    assert [m["content"] for m in msgs] == ["问题0", "问题1", "问题2"]


def test_attachment_upload_download_delete(client):
    r = client.post("/api/chat/create", json={"title": "附件测试"}, headers=_auth(ALICE_ID))
    cid = r.json()["data"]["conversation_id"]

    content = b"col_a,col_b\n1,2\n3,4"
    r = client.post(
        "/api/attachment/upload",
        data={"conversation_id": str(cid)},
        files={"file": ("销售数据.csv", content, "text/csv")},
        headers=_auth(ALICE_ID),
    )
    assert r.status_code == 200
    att = r.json()["data"]
    assert att["file_name"] == "销售数据.csv"
    assert att["file_path"].startswith(f"uploads/{ALICE_ID}/{cid}/")

    # 下载内容一致
    r = client.get("/api/attachment/get", params={"attachment_id": att["attachment_id"]},
                   headers=_auth(ALICE_ID))
    assert r.status_code == 200
    assert r.content == content

    # 附件列表 + 历史接口都会带出
    r = client.get("/api/attachment/ls", params={"conversation_id": cid}, headers=_auth(ALICE_ID))
    assert r.json()["data"]["attachments"][0]["parse_status"] == "pending"
    r = client.get(f"/api/chat/ls/{cid}", headers=_auth(ALICE_ID))
    assert len(r.json()["data"]["conversation_attachments"]) == 1

    # 删除：记录与物理文件都消失
    from pathlib import Path

    from app.services.attachment_service import attachment_abs_path

    # 先取到绝对路径再删
    async def get_abs():
        from app.db.session import SessionLocal

        async with SessionLocal() as db:
            from sqlalchemy import select

            from app.models import Attachment

            row = (await db.execute(select(Attachment).where(Attachment.id == att["attachment_id"]))).scalar_one()
            return attachment_abs_path(row)

    abs_path = asyncio.run(get_abs())
    assert Path(abs_path).is_file()
    r = client.post("/api/attachment/delete", json={"attachment_id": att["attachment_id"]},
                    headers=_auth(ALICE_ID))
    assert r.status_code == 200
    assert not Path(abs_path).exists()


def test_cross_user_isolation(client):
    r = client.post("/api/chat/create", json={"title": "alice私有的"}, headers=_auth(ALICE_ID))
    cid = r.json()["data"]["conversation_id"]

    # bob 看不到 alice 的会话
    assert client.get(f"/api/chat/ls/{cid}", headers=_auth(BOB_ID)).status_code == 404
    # bob 删不掉 alice 的会话
    r = client.post("/api/chat/delete", json={"conversation_ids": [cid]}, headers=_auth(BOB_ID))
    assert r.json()["data"]["deleted"] == []
    # alice 自己还在
    assert client.get(f"/api/chat/ls/{cid}", headers=_auth(ALICE_ID)).status_code == 200
    # 无 token 全部 401
    assert client.get("/api/chat/ls").status_code == 401


def test_cascade_delete(client):
    r = client.post("/api/chat/create", json={"title": "级联测试"}, headers=_auth(ALICE_ID))
    cid = r.json()["data"]["conversation_id"]

    client.post(
        "/api/attachment/upload",
        data={"conversation_id": str(cid)},
        files={"file": ("a.txt", b"hello", "text/plain")},
        headers=_auth(ALICE_ID),
    )

    async def append_and_get_dir():
        from app.db.session import SessionLocal
        from app.services.message_service import append_message

        async with SessionLocal() as db:
            await append_message(db, cid, role="user", content="历史消息")
            from pathlib import Path

            from app.tools._paths import BACKEND_ROOT

            return Path(BACKEND_ROOT) / "uploads" / str(ALICE_ID) / str(cid)

    upload_dir = asyncio.run(append_and_get_dir())
    assert upload_dir.is_dir()

    r = client.post("/api/chat/delete", json={"conversation_ids": [cid]}, headers=_auth(ALICE_ID))
    assert r.json()["data"]["deleted"] == [cid]

    # 会话/消息/附件全没了，目录也没了
    assert client.get(f"/api/chat/ls/{cid}", headers=_auth(ALICE_ID)).status_code == 404
    assert not upload_dir.exists()

    async def count_rows():
        from sqlalchemy import func, select

        from app.db.session import SessionLocal
        from app.models import Attachment, Message

        async with SessionLocal() as db:
            m = (await db.execute(select(func.count()).select_from(Message).where(Message.conversation_id == cid))).scalar_one()
            a = (await db.execute(select(func.count()).select_from(Attachment).where(Attachment.conversation_id == cid))).scalar_one()
        return m, a

    assert asyncio.run(count_rows()) == (0, 0)


def test_path_traversal_rejected():
    from app.models import Attachment
    from app.services.attachment_service import attachment_abs_path
    from app.core.errors import BizError

    evil = Attachment(conversation_id=1, file_path="uploads/../../secrets.txt", file_name="x")
    with pytest.raises(BizError) as ei:
        attachment_abs_path(evil)
    assert ei.value.code == "FILE_PATH_INVALID"
