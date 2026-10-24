"""结果服务：导出文件管理与归属校验。"""
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import BizError
from ..models import AnalysisResult, AnalysisTask
from ..tools import _paths


def export_result(user_id: int, conversation_id: int, task_id: int, markdown: str) -> str:
    """写 exports/{user}/{conv}/{task_id}.md，返回相对 file_path（正斜杠）。"""
    d = _paths.EXPORTS_ROOT / str(user_id) / str(conversation_id)
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{task_id}.md"
    p.write_text(markdown, encoding="utf-8", newline="\n")
    return f"exports/{user_id}/{conversation_id}/{task_id}.md"


def export_abs_path(rel_path: str) -> Path:
    """带前缀 file_path → 越界校验后的绝对路径。"""
    return _paths.resolve_stored_path(rel_path)


async def get_owned_result(db: AsyncSession, task_id: int, user_id: int) -> AnalysisResult:
    result = (
        await db.execute(
            select(AnalysisResult)
            .join(AnalysisTask, AnalysisResult.task_id == AnalysisTask.id)
            .where(AnalysisResult.task_id == task_id, AnalysisTask.user_id == user_id)
        )
    ).scalar_one_or_none()
    if result is None:
        raise BizError("RESULT_NOT_FOUND", "分析结果不存在", 404)
    return result


async def get_latest_result(db: AsyncSession, conversation_id: int, user_id: int) -> AnalysisResult | None:
    conv = (
        await db.execute(
            select(AnalysisTask.user_id).where(AnalysisTask.conversation_id == conversation_id)
        )
    ).first()
    if conv is None or conv[0] != user_id:
        raise BizError("CONV_NOT_FOUND", "会话不存在", 404)
    return (
        await db.execute(
            select(AnalysisResult)
            .where(AnalysisResult.conversation_id == conversation_id)
            .order_by(AnalysisResult.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def result_payload(r: AnalysisResult) -> dict:
    return {
        "task_id": r.task_id,
        "result_id": r.id,
        "problem_definition": r.problem_definition,
        "key_metrics": r.key_metrics_json,
        "evidence_list": r.evidence_list_json,
        "conclusion_text": r.conclusion_text,
        "missing_data_text": r.missing_data_text,
        "next_action_text": r.next_action_text,
        "result_markdown": r.result_markdown,
        "result_file_path": r.result_file_path,
        "created_at": r.created_at,
    }
