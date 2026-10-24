"""消息服务：顺序控制（seq_no 会话内自增）与追加写入。"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Conversation, Message


async def next_seq_no(db: AsyncSession, conversation_id: int) -> int:
    """取会话内下一个 seq_no。调用方应先锁定会话行保证串行（MySQL 下 FOR UPDATE 生效）。"""
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
    """追加一条消息并更新会话 last_message_at。

    seq_no 冲突由 uq_messages_conv_seq 兜底；MySQL 部署时先 FOR UPDATE 会话行。
    """
    await db.execute(
        select(Conversation.id).where(Conversation.id == conversation_id).with_for_update()
    )
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
    conv = (
        await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    ).scalar_one()
    conv.last_message_at = func.now()
    await db.commit()
    await db.refresh(msg)
    return msg
