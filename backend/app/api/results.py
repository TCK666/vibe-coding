"""结果模块接口骨架（里程碑6实现：结构化结果查询）。"""
from fastapi import APIRouter

from ..core.errors import BizError

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/{task_id}", summary="查询分析结果")
async def get_result(task_id: int):
    raise BizError("NOT_IMPLEMENTED", "结果接口在里程碑6实现", 501)
