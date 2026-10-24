"""任务模块接口：任务状态查询（里程碑5实现）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..core.errors import BizError, ok
from ..db.session import get_db
from ..models import AnalysisTask, User

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}", summary="查询分析任务状态")
async def get_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    task = (
        await db.execute(
            select(AnalysisTask).where(
                AnalysisTask.id == task_id, AnalysisTask.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if task is None:
        raise BizError("TASK_NOT_FOUND", "任务不存在", 404)
    return ok(
        {
            "task_id": task.id,
            "conversation_id": task.conversation_id,
            "task_status": task.task_status,
            "current_step": task.current_step,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "error_message": task.error_message,
        }
    )
