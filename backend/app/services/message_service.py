"""消息服务：顺序控制（seq_no 会话内自增）与追加写入。

seq 读取与插入分两段：避免 SQLite"读事务升级写锁"的瞬时 BUSY；
并发插入的序号冲突由 uq_messages_conv_seq 唯一约束兜底并重试。
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Conversation, Message

_SEQ_RETRY = 3


async def next_seq_no(db: AsyncSession, conversation_id: int) -> int:
    current = (
        await db.execute(
            select(func.max(Message.seq_no)).where(Message.conversation_id == conversation_id)
        )
    ).scalar_one()
    return (current or 0) + 1


async def append_message(
    db: AsyncSession,
    conversation_id: int,
    role: str,
    message_type: str = "text",
    content: Optional[str] = None,
    tool_name: Optional[str] = None,
    tool_status: Optional[str] = None,
) -> Message:
    """追加一条消息并更新会话 last_message_at。seq 冲突时重取重试。"""
    for attempt in range(_SEQ_RETRY):
        seq = await next_seq_no(db, conversation_id)
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            message_type=message_type,
            content=content,
            tool_name=tool_name,
            tool_status=tool_status,
            seq_no=seq,
        )
        db.add(msg)
        try:
            conv = (
                await db.execute(select(Conversation).where(Conversation.id == conversation_id))
            ).scalar_one()
            conv.last_message_at = func.now()
            await db.commit()
            await db.refresh(msg)
            return msg
        except IntegrityError:
            await db.rollback()
            if attempt == _SEQ_RETRY - 1:
                raise
    raise RuntimeError("unreachable")
