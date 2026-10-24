"""异步数据库会话。开发期默认 SQLite，MySQL 部署改 BAAS_DB_URL 并用 alembic 迁移。"""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ..core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(get_settings().db_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    # 开发期直接 create_all；MySQL 部署时改用 alembic（sql/01_init.sql 为同构 DDL）
    from .. import models  # noqa: F401  确保模型注册到 Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
