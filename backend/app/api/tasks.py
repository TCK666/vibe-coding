"""任务模块接口骨架（里程碑5实现：任务状态查询）。"""
from fastapi import APIRouter

from ..core.errors import BizError

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}", summary="查询分析任务状态")
async def get_task(task_id: int):
    raise BizError("NOT_IMPLEMENTED", "任务接口在里程碑5实现", 501)
