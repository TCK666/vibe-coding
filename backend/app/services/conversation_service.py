"""会话服务：CRUD、归属校验、级联删除（含物理目录清理）。"""
import shutil
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import BizError
from ..models import (
    AnalysisResult,
    AnalysisTask,
    Attachment,
    ContextSummary,
    Conversation,
    Message,
    TaskLog,
    WebsocketToken,
)
from ..tools import _paths

BACKEND_ROOT = _paths.BACKEND_ROOT


async def create_conversation(db: AsyncSession, user_id: int, title: str) -> Conversation:
    conv = Conversation(user_id=user_id, title=title or "未命名会话")
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def list_conversations(db: AsyncSession, user_id: int) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id, Conversation.status != "deleted")
        .order_by(Conversation.last_message_at.desc().nullslast(), Conversation.id.desc())
    )
    return list(result.scalars().all())


async def get_owned_conversation(
    db: AsyncSession, conversation_id: int, user_id: int
) -> Conversation:
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise BizError("CONV_NOT_FOUND", "会话不存在", 404)
    return conv


async def rename_conversation(db: AsyncSession, conv: Conversation, title: str) -> None:
    conv.title = title
    await db.commit()


async def delete_conversations_cascade(
    db: AsyncSession, user_id: int, conversation_ids: list[int]
) -> list[int]:
    """物理级联删除本人会话：级联记录 → 会话行 → 提交 → 物理目录。返回实际删除的 id。"""
    deleted: list[int] = []
    for cid in conversation_ids:
        conv = (
            await db.execute(
                select(Conversation).where(
                    Conversation.id == cid, Conversation.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        if conv is None:
            continue

        # 1. WS 令牌
        await db.execute(delete(WebsocketToken).where(WebsocketToken.conversation_id == cid))
        # 2. 任务日志（经 task_ids）
        task_ids = (
            await db.execute(select(AnalysisTask.id).where(AnalysisTask.conversation_id == cid))
        ).scalars().all()
        if task_ids:
            await db.execute(delete(TaskLog).where(TaskLog.task_id.in_(task_ids)))
        # 3. 结果 → 任务 → 摘要 → 消息 → 附件记录
        await db.execute(delete(AnalysisResult).where(AnalysisResult.conversation_id == cid))
        await db.execute(delete(AnalysisTask).where(AnalysisTask.conversation_id == cid))
        await db.execute(delete(ContextSummary).where(ContextSummary.conversation_id == cid))
        await db.execute(delete(Message).where(Message.conversation_id == cid))
        await db.execute(delete(Attachment).where(Attachment.conversation_id == cid))
        # 4. 会话行
        await db.execute(delete(Conversation).where(Conversation.id == cid))
        deleted.append(cid)

    await db.commit()

    # 5. 物理目录（记录已落定，删目录失败不影响事务）
    for cid in deleted:
        for sub in ("uploads", "exports", "workspace"):
            target = Path(BACKEND_ROOT) / sub / str(user_id) / str(cid)
            shutil.rmtree(target, ignore_errors=True)
    return deleted


async def count_conversations(db: AsyncSession, user_id: int) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(Conversation)
            .where(Conversation.user_id == user_id)
        )
    ).scalar_one()
