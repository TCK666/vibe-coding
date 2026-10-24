"""运行期配置服务：system_configs 表为唯一来源，进程内缓存加速同步读取。

热更新：POST /api/admin/reload 重建缓存；set_value 同步写 DB 与缓存。
"""
from sqlalchemy import select

from ..db.session import SessionLocal
from ..models import SystemConfig

_cache: dict[str, str] = {}

DEFAULT_CONFIGS: list[tuple[str, str, str]] = [
    ("llm.provider", "mock", "llm"),
    ("llm.base_url", "http://127.0.0.1:9002", "llm"),
    ("llm.model", "mock-attribution", "llm"),
    ("llm.api_key", "mock-key", "llm"),
    ("analysis.max_tool_calls", "8", "analysis"),
    ("analysis.context_threshold", "8000", "analysis"),
    ("ws.token_ttl_seconds", "30", "ws"),
    ("tool.cmd.whitelist", "python,ping,dir", "tool"),
    ("tool.db_query.readonly_dsn", "", "tool"),
]


async def seed_defaults() -> None:
    """启动时补齐默认配置项（已存在的不覆盖）。"""
    async with SessionLocal() as db:
        for key, value, group in DEFAULT_CONFIGS:
            exists = (
                await db.execute(
                    select(SystemConfig.id).where(SystemConfig.config_key == key)
                )
            ).scalar_one_or_none()
            if exists is None:
                db.add(SystemConfig(config_key=key, config_value=value, config_group=group))
        await db.commit()


async def reload_cache() -> int:
    """全量重读 DB 重建缓存，返回条数。"""
    async with SessionLocal() as db:
        rows = (await db.execute(select(SystemConfig))).scalars().all()
    _cache.clear()
    for r in rows:
        _cache[r.config_key] = r.config_value or ""
    return len(_cache)


async def set_value(key: str, value: str, group: str = "default") -> None:
    """upsert 单项并同步缓存。"""
    async with SessionLocal() as db:
        row = (
            await db.execute(select(SystemConfig).where(SystemConfig.config_key == key))
        ).scalar_one_or_none()
        if row is None:
            db.add(SystemConfig(config_key=key, config_value=value, config_group=group))
        else:
            row.config_value = value
        await db.commit()
    _cache[key] = value


async def list_all() -> list[SystemConfig]:
    async with SessionLocal() as db:
        rows = (
            await db.execute(select(SystemConfig).order_by(SystemConfig.config_group, SystemConfig.config_key))
        ).scalars().all()
        return list(rows)


def get_sync(key: str, default: str = "") -> str:
    """运行期同步读取（缓存未命中回落默认值）。"""
    return _cache.get(key, default)


def get_sync_int(key: str, default: int) -> int:
    try:
        return int(get_sync(key, str(default)))
    except (TypeError, ValueError):
        return default
