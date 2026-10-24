"""认证接入模块：对接认证中心（开发期 mock_auth，可切真实认证中心）建立本系统登录态。

流程：/auth/login 302 → 认证中心授权 → /auth/callback 换令牌+拉用户信息 →
users 表 upsert → 签发本系统 JWT → 302 回前端 /auth/callback?access_token=...
"""
import secrets
import time

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import get_settings
from ..core.deps import get_current_user
from ..core.errors import BizError, ok
from ..core.security import create_access_token
from ..db.session import get_db
from ..services.user_service import upsert_from_userinfo

router = APIRouter(tags=["auth"])


@router.get("/api/auth/me", summary="当前登录用户")
async def me(user=Depends(get_current_user)):
    return ok(
        {
            "user_id": user.id,
            "external_user_id": user.external_user_id,
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role,
        }
    )

# OAuth state 防CSRF：内存态，5 分钟有效
_states: dict[str, float] = {}


def _new_state() -> str:
    now = time.time()
    for k in [k for k, exp in _states.items() if exp < now]:
        _states.pop(k, None)
    state = secrets.token_urlsafe(16)
    _states[state] = now + 300
    return state


def _callback_url() -> str:
    return f"{get_settings().public_base_url}/auth/callback"


@router.get("/auth/login", summary="跳转认证中心发起授权登录")
async def login():
    s = get_settings()
    url = (
        f"{s.auth_base_url}/oauth/authorize"
        f"?response_type=code&client_id={s.auth_client_id}"
        f"&redirect_uri={_callback_url()}&state={_new_state()}&scope=profile"
    )
    return RedirectResponse(url, status_code=302)


@router.get("/auth/callback", summary="处理授权回调并建立登录态")
async def auth_callback(
    code: str = "",
    state: str = "",
    db: AsyncSession = Depends(get_db),
):
    s = get_settings()
    if not code or not state or _states.pop(state, None) is None:
        raise BizError("AUTH_STATE_INVALID", "授权状态校验失败，请重新登录", 400)

    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            f"{s.auth_base_url}/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": _callback_url(),
                "client_id": s.auth_client_id,
                "client_secret": s.auth_client_secret,
            },
        )
    if token_resp.status_code != 200:
        raise BizError("AUTH_EXCHANGE_FAILED", f"换取访问令牌失败：{token_resp.text[:200]}", 401)
    access_token = token_resp.json()["access_token"]

    async with httpx.AsyncClient(timeout=10) as client:
        userinfo_resp = await client.get(
            f"{s.auth_base_url}/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if userinfo_resp.status_code != 200:
        raise BizError("AUTH_USERINFO_FAILED", "获取用户信息失败", 401)

    user = await upsert_from_userinfo(db, userinfo_resp.json())
    baas_token, expires_in = create_access_token(user.id, user.external_user_id, user.role)

    return RedirectResponse(
        f"{s.frontend_base_url}/auth/callback?access_token={baas_token}&expires_in={expires_in}",
        status_code=302,
    )
