"""会话模块接口（里程碑4实现）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..core.errors import ok
from ..db.session import get_db
from ..models import Attachment, Message, User
from ..schemas.chat import (
    CreateConversationReq,
    DeleteConversationsReq,
    UpdateConversationReq,
)
from ..services import conversation_service, message_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/create", summary="创建会话")
async def create_conversation(
    req: CreateConversationReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await conversation_service.create_conversation(db, user.id, req.title)
    return ok({"conversation_id": conv.id, "title": conv.title, "status": conv.status})


@router.post("/delete", summary="删除会话（级联删除记录与文件目录）")
async def delete_conversations(
    req: DeleteConversationsReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await conversation_service.delete_conversations_cascade(
        db, user.id, req.conversation_ids
    )
    return ok({"deleted": deleted})


@router.post("/update", summary="重命名会话")
async def update_conversation(
    req: UpdateConversationReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await conversation_service.get_owned_conversation(db, req.conversation_id, user.id)
    await conversation_service.rename_conversation(db, conv, req.title)
    return ok({"conversation_id": conv.id, "title": conv.title, "status": conv.status})


@router.get("/ls", summary="会话列表")
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    convs = await conversation_service.list_conversations(db, user.id)
    return ok(
        {
            "conversations": [
                {
                    "conversation_id": c.id,
                    "title": c.title,
                    "status": c.status,
                    "last_message_at": c.last_message_at,
                }
                for c in convs
            ]
        }
    )


@router.get("/ls/{conversation_id}", summary="历史消息与会话附件")
async def list_messages(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    conv = await conversation_service.get_owned_conversation(db, conversation_id, user.id)
    result = await db.execute(
        select(Attachment).where(Attachment.conversation_id == conv.id).order_by(Attachment.id)
    )
    all_atts = list(result.scalars().all())
    by_message: dict[int, list[Attachment]] = {}
    conv_atts: list[Attachment] = []
    for a in all_atts:
        if a.message_id:
            by_message.setdefault(a.message_id, []).append(a)
        else:
            conv_atts.append(a)

    msgs = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.seq_no)
        )
    ).scalars().all()

    def att_item(a: Attachment):
        return {
            "attachment_id": a.id,
            "file_name": a.file_name,
            "file_type": a.file_type,
            "file_size": a.file_size,
            "parse_status": a.parse_status,
            "created_at": a.created_at,
        }

    return ok(
        {
            "conversation": {
                "conversation_id": conv.id,
                "title": conv.title,
                "status": conv.status,
                "last_message_at": conv.last_message_at,
            },
            "messages": [
                {
                    "message_id": m.id,
                    "role": m.role,
                    "message_type": m.message_type,
                    "content": m.content,
                    "seq_no": m.seq_no,
                    "attachments": [att_item(a) for a in by_message.get(m.id, [])],
                    "created_at": m.created_at,
                }
                for m in msgs
            ],
            "conversation_attachments": [att_item(a) for a in conv_atts],
        }
    )
