"""依赖注入：当前用户识别。"""
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..models import User
from .errors import BizError
from .security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if cred is None:
        raise BizError("AUTH_TOKEN_MISSING", "缺少访问令牌", 401)
    payload = decode_access_token(cred.credentials)
    user = (
        await db.execute(select(User).where(User.id == int(payload["sub"])))
    ).scalar_one_or_none()
    if user is None or user.status != "active":
        raise BizError("AUTH_USER_INVALID", "用户不存在或已禁用", 401)
    return user


async def get_current_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise BizError("AUTH_FORBIDDEN", "需要系统管理员权限", 403)
    return user
