"""配置模块接口骨架（里程碑7实现：配置读取与热更新）。"""
from fastapi import APIRouter

from ..core.errors import BizError

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/reload", summary="重载系统配置（热更新）")
async def reload_config():
    raise BizError("NOT_IMPLEMENTED", "配置接口在里程碑7实现", 501)
