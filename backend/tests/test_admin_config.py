"""里程碑7 验收：配置热更新 / 管理员权限 / 日志查询。"""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.services import config_service

ADMIN = {"sub": "u-admin", "username": "admin", "display_name": "管理员", "role": "admin"}
ALICE = {"sub": "u-alice7", "username": "alice7", "display_name": "A7", "role": "user"}


def _setup():
    async def run():
        from app.db.session import SessionLocal, init_db
        from app.services.user_service import upsert_from_userinfo

        await init_db()
        async with SessionLocal() as db:
            admin = await upsert_from_userinfo(db, ADMIN)
            alice = await upsert_from_userinfo(db, ALICE)
        await config_service.seed_defaults()
        await config_service.reload_cache()
        return admin.id, alice.id

    return asyncio.run(run())


ADMIN_ID, ALICE_ID = _setup()


def _auth(uid, ext=None):
    token, _ = create_access_token(uid, ext or f"u-{uid}", "admin" if uid == ADMIN_ID else "user")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_non_admin_forbidden(client):
    for path in ("/api/admin/configs", "/api/admin/logs"):
        assert client.get(path, headers=_auth(ALICE_ID)).status_code == 403
    for path in ("/api/admin/reload", "/api/admin/configs"):
        assert client.post(path, json={}, headers=_auth(ALICE_ID)).status_code == 403
    assert client.get("/api/admin/configs").status_code == 401


def test_config_list_seeded(client):
    r = client.get("/api/admin/configs", headers=_auth(ADMIN_ID))
    assert r.status_code == 200
    keys = {c["config_key"] for c in r.json()["data"]["configs"]}
    assert {"llm.provider", "llm.base_url", "analysis.context_threshold",
            "tool.cmd.whitelist", "ws.token_ttl_seconds"} <= keys


def test_set_and_reload_hot_update(client):
    # 1. set_value 立即生效（缓存同步）
    r = client.post(
        "/api/admin/configs",
        json={"config_key": "llm.model", "config_value": "test-model-v2"},
        headers=_auth(ADMIN_ID),
    )
    assert r.status_code == 200
    assert config_service.get_sync("llm.model", "") == "test-model-v2"

    # 2. LLM 工厂读取缓存
    from app.llm import get_llm_client

    assert get_llm_client().model == "test-model-v2"

    # 3. 直接改 DB（绕过缓存）→ reload 后同步
    async def db_update():
        from sqlalchemy import update

        from app.db.session import SessionLocal
        from app.models import SystemConfig

        async with SessionLocal() as db:
            await db.execute(
                update(SystemConfig)
                .where(SystemConfig.config_key == "llm.model")
                .values(config_value="db-edited-model")
            )
            await db.commit()

    asyncio.run(db_update())
    assert config_service.get_sync("llm.model", "") == "test-model-v2"  # 仍是旧缓存
    r = client.post("/api/admin/reload", headers=_auth(ADMIN_ID))
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["status"] == "ok" and "重载" in body["message"]
    assert config_service.get_sync("llm.model", "") == "db-edited-model"

    # 还原
    client.post("/api/admin/configs", json={"config_key": "llm.model", "config_value": "mock-attribution"},
                headers=_auth(ADMIN_ID))


def test_logs_query(client):
    task_id = 777001

    async def seed():
        from app.db.session import SessionLocal
        from app.models import TaskLog

        async with SessionLocal() as db:
            db.add(TaskLog(task_id=task_id, log_level="INFO", log_type="state_change", log_content="诊断日志A"))
            db.add(TaskLog(task_id=task_id + 1, log_level="ERROR", log_type="error", log_content="诊断日志B"))
            await db.commit()

    asyncio.run(seed())

    r = client.get("/api/admin/logs", headers=_auth(ADMIN_ID))
    assert r.status_code == 200
    logs = r.json()["data"]["logs"]
    assert any(l["log_content"] == "诊断日志A" for l in logs)

    r = client.get(f"/api/admin/logs?task_id={task_id}", headers=_auth(ADMIN_ID))
    logs = r.json()["data"]["logs"]
    assert len(logs) == 1 and logs[0]["log_content"] == "诊断日志A"
