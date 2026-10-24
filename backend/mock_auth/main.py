"""mock 认证中心：模拟 OAuth2 授权码模式，接口形状与真实认证中心一致。

预置账号：
  tangck / 123456    分析用户(role=user)
  admin  / admin123  系统管理员(role=admin)

启动: .venv/Scripts/python -m uvicorn mock_auth.main:app --app-dir backend --port 9001
"""
import secrets
import time

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jose import jwt

SECRET = "mock-auth-hs256-secret"
TOKEN_TTL = 3600
CODE_TTL = 120

CLIENTS = {
    "baas-web": {
        "client_secret": "baas-web-secret",
        "redirect_uris": [
            "http://localhost:8000/auth/callback",
            "http://127.0.0.1:8000/auth/callback",
        ],
    }
}

USERS = {
    "tangck": {
        "password": "123456",
        "sub": "u-tangck",
        "display_name": "唐同学（分析用户）",
        "role": "user",
    },
    "admin": {
        "password": "admin123",
        "sub": "u-admin",
        "display_name": "系统管理员",
        "role": "admin",
    },
}

app = FastAPI(title="mock-auth-center")

_auth_codes: dict[str, dict] = {}
_sessions: dict[str, str] = {}  # session_id -> username
_used_codes: set[str] = set()


def _issue_code(client_id: str, redirect_uri: str, username: str, state: str) -> str:
    code = secrets.token_urlsafe(24)
    _auth_codes[code] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "username": username,
        "state": state,
        "expires": time.time() + CODE_TTL,
    }
    return code


def _redirect_with_code(redirect_uri: str, code: str, state: str) -> RedirectResponse:
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(f"{redirect_uri}{sep}code={code}&state={state}", status_code=302)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "mock-auth"}


@app.get("/oauth/authorize")
async def authorize(
    request: Request,
    response_type: str = "code",
    client_id: str = "",
    redirect_uri: str = "",
    state: str = "",
    scope: str = "",
):
    client = CLIENTS.get(client_id)
    if not client or response_type != "code":
        raise HTTPException(status_code=400, detail="invalid client_id or response_type")
    if redirect_uri not in client["redirect_uris"]:
        raise HTTPException(status_code=400, detail=f"redirect_uri 未注册: {redirect_uri}")

    username = _sessions.get(request.cookies.get("ma_session", ""), "")
    if username:
        code = _issue_code(client_id, redirect_uri, username, state)
        return _redirect_with_code(redirect_uri, code, state)

    html = f"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>认证中心登录</title></head>
<body style="font-family:sans-serif;display:flex;justify-content:center;padding-top:80px;background:#f5f6f7;">
<div style="width:340px;background:#fff;border:1px solid #ddd;border-radius:8px;padding:28px;">
<h2 style="margin-top:0;">认证中心（mock）</h2>
<p style="color:#888;font-size:13px;">预置账号：tangck/123456（分析用户）、admin/admin123（管理员）</p>
<form method="post" action="/oauth/login">
  <input type="hidden" name="client_id" value="{client_id}">
  <input type="hidden" name="redirect_uri" value="{redirect_uri}">
  <input type="hidden" name="state" value="{state}">
  <p><input name="username" placeholder="用户名" value="tangck" style="width:100%;padding:8px;box-sizing:border-box;"></p>
  <p><input name="password" type="password" placeholder="密码" style="width:100%;padding:8px;box-sizing:border-box;"></p>
  <button type="submit" style="width:100%;padding:10px;background:#409eff;color:#fff;border:0;border-radius:4px;cursor:pointer;">授权并登录</button>
</form>
</div></body></html>"""
    return HTMLResponse(html)


@app.post("/oauth/login")
async def login(
    username: str = Form(""),
    password: str = Form(""),
    client_id: str = Form(""),
    redirect_uri: str = Form(""),
    state: str = Form(""),
):
    user = USERS.get(username)
    if not user or user["password"] != password:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    client = CLIENTS.get(client_id)
    if not client or redirect_uri not in client["redirect_uris"]:
        raise HTTPException(status_code=400, detail="redirect_uri 未注册")

    session_id = secrets.token_urlsafe(24)
    _sessions[session_id] = username
    code = _issue_code(client_id, redirect_uri, username, state)
    resp = _redirect_with_code(redirect_uri, code, state)
    resp.set_cookie("ma_session", session_id, httponly=True, samesite="lax")
    return resp


@app.post("/oauth/token")
async def token(request: Request):
    form = await request.form()
    client_id = str(form.get("client_id", ""))
    client_secret = str(form.get("client_secret", ""))
    code = str(form.get("code", ""))
    redirect_uri = str(form.get("redirect_uri", ""))

    client = CLIENTS.get(client_id)
    if not client or client_secret != client["client_secret"]:
        raise HTTPException(status_code=401, detail="invalid client")
    data = _auth_codes.get(code)
    if not data or code in _used_codes or data["expires"] < time.time():
        raise HTTPException(status_code=400, detail="invalid or expired code")
    if data["redirect_uri"] != redirect_uri:
        raise HTTPException(status_code=400, detail="redirect_uri mismatch")
    _used_codes.add(code)

    user = USERS[data["username"]]
    now = int(time.time())
    access_token = jwt.encode(
        {
            "sub": user["sub"],
            "username": data["username"],
            "display_name": user["display_name"],
            "role": user["role"],
            "iat": now,
            "exp": now + TOKEN_TTL,
        },
        SECRET,
        algorithm="HS256",
    )
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL,
        "refresh_token": secrets.token_urlsafe(32),
        "scope": "profile",
    }


@app.get("/userinfo")
async def userinfo(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        payload = jwt.decode(authorization[7:], SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")
    return {
        "sub": payload["sub"],
        "username": payload["username"],
        "display_name": payload["display_name"],
        "role": payload["role"],
    }


@app.post("/oauth/introspect")
async def introspect(request: Request):
    form = await request.form()
    token_value = str(form.get("token", ""))
    try:
        payload = jwt.decode(token_value, SECRET, algorithms=["HS256"])
        return {"active": payload["exp"] > time.time(), "sub": payload["sub"], "role": payload["role"]}
    except Exception:
        return {"active": False}
