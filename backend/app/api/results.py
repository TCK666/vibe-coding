"""结果模块接口（里程碑6实现）。"""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..core.errors import BizError, ok
from ..db.session import get_db
from ..models import User
from ..services import result_service

router = APIRouter(prefix="/api/results", tags=["results"])


@router.get("/latest/{conversation_id}", summary="会话内最新分析结果")
async def latest_result(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await result_service.get_latest_result(db, conversation_id, user.id)
    return ok({"result": result_service.result_payload(r) if r else None})


@router.get("/{task_id}", summary="查询分析结果")
async def get_result(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await result_service.get_owned_result(db, task_id, user.id)
    return ok(result_service.result_payload(r))


@router.get("/{task_id}/download", summary="下载结果导出文件")
async def download_result(
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    r = await result_service.get_owned_result(db, task_id, user.id)
    if not r.result_file_path:
        raise BizError("RESULT_FILE_MISSING", "该结果没有导出文件", 404)
    abs_path = result_service.export_abs_path(r.result_file_path)
    if not abs_path.is_file():
        raise BizError("RESULT_FILE_MISSING", "导出文件已丢失", 404)
    return FileResponse(abs_path, filename=f"analysis_{task_id}.md")
