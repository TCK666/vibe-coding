"""异步数据库会话。开发期默认 SQLite，MySQL 部署改 BAAS_DB_URL 并用 alembic 迁移。

SQLite 开发库：
- WAL + 加大 busy timeout：任务引擎存在多连接并发写，默认模式极易 "database is locked"
- NullPool：aiosqlite 连接绑定创建它的事件循环，连接池跨循环复用（如测试端每个
  WebSocket 会话独立 portal）会永久悬挂；SQLite 建连成本低，禁用池最稳。
"""
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from ..core.config import get_settings


class Base(DeclarativeBase):
    pass


_settings = get_settings()
_is_sqlite = _settings.db_url.startswith("sqlite")

engine = create_async_engine(
    _settings.db_url,
    echo=False,
    **({"connect_args": {"timeout": 30}, "poolclass": NullPool} if _is_sqlite else {}),
)

if _is_sqlite:

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    # 开发期直接 create_all；MySQL 部署时改用 alembic（sql/01_init.sql 为同构 DDL）
    from .. import models  # noqa: F401  确保模型注册到 Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
