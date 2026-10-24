"""配置模块接口（里程碑7实现）：配置查看/修改、热更新、运行日志。"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_admin_user
from ..core.errors import ok
from ..db.session import get_db
from ..models import TaskLog, User
from ..services import config_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


class SetConfigReq(BaseModel):
    config_key: str
    config_value: str


@router.get("/configs", summary="查看全部系统配置")
async def list_configs(admin: User = Depends(get_current_admin_user)):
    rows = await config_service.list_all()
    return ok(
        {
            "configs": [
                {
                    "config_key": r.config_key,
                    "config_value": r.config_value,
                    "config_group": r.config_group,
                    "updated_at": r.updated_at,
                }
                for r in rows
            ]
        }
    )


@router.post("/configs", summary="修改配置项（立即生效）")
async def set_config(
    req: SetConfigReq,
    admin: User = Depends(get_current_admin_user),
):
    group = req.config_key.split(".")[0] if "." in req.config_key else "default"
    await config_service.set_value(req.config_key, req.config_value, group)
    return ok({"config_key": req.config_key, "config_value": req.config_value})


@router.post("/reload", summary="重载系统配置（热更新）")
async def reload_config(admin: User = Depends(get_current_admin_user)):
    count = await config_service.reload_cache()
    return ok({"status": "ok", "message": f"已重载 {count} 项配置并即时生效"})


@router.get("/logs", summary="查询运行日志（task_logs）")
async def list_logs(
    task_id: int | None = Query(default=None),
    limit: int = Query(default=200, le=1000),
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(TaskLog).order_by(TaskLog.id.desc()).limit(limit)
    if task_id is not None:
        stmt = (
            select(TaskLog)
            .where(TaskLog.task_id == task_id)
            .order_by(TaskLog.id.desc())
            .limit(limit)
        )
    rows = (await db.execute(stmt)).scalars().all()
    return ok(
        {
            "logs": [
                {
                    "log_id": r.id,
                    "task_id": r.task_id,
                    "log_level": r.log_level,
                    "log_type": r.log_type,
                    "log_content": r.log_content,
                    "created_at": r.created_at,
                }
                for r in rows
            ]
        }
    )
