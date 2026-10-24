"""里程碑2 地基验收：健康检查、mock 认证全流程、mock LLM 流式、模型建表。"""
import asyncio
import json

from fastapi.testclient import TestClient

from app.main import app
from mock_auth.main import app as auth_app
from mock_llm.main import app as llm_app

REDIRECT_URI = "http://localhost:8000/auth/callback"


def test_backend_healthz_and_auth_guard():
    with TestClient(app) as client:
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # 里程碑4起会话接口已实现：无令牌一律 401
        resp = client.post("/api/chat/create", json={"title": "冒烟测试"})
        assert resp.status_code == 401
        assert resp.json()["code"] == "AUTH_TOKEN_MISSING"

        # 管理接口同样需要令牌（里程碑7已实装）
        resp = client.post("/api/admin/reload")
        assert resp.status_code == 401


def test_mock_auth_full_oauth2_flow():
    with TestClient(auth_app) as client:
        # 1. 未登录 → 授权端点返回登录表单
        r = client.get(
            "/oauth/authorize",
            params={
                "response_type": "code",
                "client_id": "baas-web",
                "redirect_uri": REDIRECT_URI,
                "state": "s1",
            },
        )
        assert r.status_code == 200
        assert "认证中心" in r.text

        # 2. 表单登录 → 302 回回调地址并携带 code
        r = client.post(
            "/oauth/login",
            data={
                "username": "tangck",
                "password": "123456",
                "client_id": "baas-web",
                "redirect_uri": REDIRECT_URI,
                "state": "s1",
            },
            follow_redirects=False,
        )
        assert r.status_code == 302
        assert "code=" in r.headers["location"]
        auth_code = r.headers["location"].split("code=")[1].split("&")[0]

        # 3. code 换令牌（错误 secret 必须被拒）
        r = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": REDIRECT_URI,
                "client_id": "baas-web",
                "client_secret": "wrong-secret",
            },
        )
        assert r.status_code == 401

        r = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": REDIRECT_URI,
                "client_id": "baas-web",
                "client_secret": "baas-web-secret",
            },
        )
        assert r.status_code == 200
        access_token = r.json()["access_token"]

        # 4. code 一次性：复用必须失败
        r = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": REDIRECT_URI,
                "client_id": "baas-web",
                "client_secret": "baas-web-secret",
            },
        )
        assert r.status_code == 400

        # 5. userinfo
        r = client.get("/userinfo", headers={"Authorization": f"Bearer {access_token}"})
        assert r.status_code == 200
        assert r.json()["sub"] == "u-tangck"
        assert r.json()["role"] == "user"


def test_mock_llm_tool_call_then_final_content():
    with TestClient(llm_app) as client:
        # 第一轮：应返回 db_query 工具调用
        body = {
            "model": "m",
            "stream": True,
            "messages": [{"role": "user", "content": "近30天下单转化率如何？"}],
            "tools": [{"type": "function", "function": {"name": "db_query"}}],
        }
        chunks = []
        with client.stream("POST", "/v1/chat/completions", json=body) as r:
            for line in r.iter_lines():
                if line.startswith("data:") and line[5:].strip() != "[DONE]":
                    chunks.append(json.loads(line[5:]))
        args = "".join(
            (c["choices"][0]["delta"].get("tool_calls") or [{}])[0]
            .get("function", {})
            .get("arguments", "")
            for c in chunks
            if c["choices"][0]["delta"].get("tool_calls")
        )
        assert "biz_visit_event" in args
        assert any(c["choices"][0]["finish_reason"] == "tool_calls" for c in chunks)

        # 第二轮：带 tool 结果 → 流式输出六部分 JSON
        body2 = {
            "model": "m",
            "stream": True,
            "messages": [
                {"role": "user", "content": "近30天下单转化率如何？"},
                {"role": "tool", "content": "query rows..."},
            ],
        }
        text = ""
        with client.stream("POST", "/v1/chat/completions", json=body2) as r:
            for line in r.iter_lines():
                if line.startswith("data:") and line[5:].strip() != "[DONE]":
                    delta = json.loads(line[5:])["choices"][0]["delta"]
                    text += delta.get("content") or ""
        assert "problem_definition" in text and "next_action_text" in text


def test_models_create_all_and_query():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.db.session import Base
    from app.models import User

    async def run():
        engine = create_async_engine("sqlite+aiosqlite://")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as s:
            s.add(User(external_user_id="u-x", username="x"))
            await s.commit()
            got = (
                await s.execute(select(User).where(User.external_user_id == "u-x"))
            ).scalar_one()
            assert got.role == "user"
        await engine.dispose()

    asyncio.run(run())
