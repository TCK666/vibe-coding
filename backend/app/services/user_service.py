"""用户服务：认证中心用户信息 → users 表 upsert。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import User


async def upsert_from_userinfo(db: AsyncSession, info: dict) -> User:
    external_id = str(info["sub"])
    user = (
        await db.execute(select(User).where(User.external_user_id == external_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            external_user_id=external_id,
            username=info.get("username", external_id),
            display_name=info.get("display_name", ""),
            role=info.get("role", "user"),
        )
        db.add(user)
    else:
        user.username = info.get("username", user.username)
        user.display_name = info.get("display_name", user.display_name)
        user.role = info.get("role", user.role)
    await db.commit()
    await db.refresh(user)
    return user
