"""会话/消息/附件模块出入参模型。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateConversationReq(BaseModel):
    title: str = Field(default="未命名会话", max_length=256)


class UpdateConversationReq(BaseModel):
    conversation_id: int
    title: str = Field(max_length=256)


class DeleteConversationsReq(BaseModel):
    conversation_ids: list[int]


class DeleteAttachmentReq(BaseModel):
    attachment_id: int


class AttachmentItem(BaseModel):
    attachment_id: int
    file_name: str
    file_type: str
    file_size: int
    parse_status: str
    created_at: Optional[datetime] = None


class MessageItem(BaseModel):
    message_id: int
    role: str
    message_type: str
    content: Optional[str] = None
    seq_no: int
    attachments: list[AttachmentItem] = []
    created_at: Optional[datetime] = None


class ConversationItem(BaseModel):
    conversation_id: int
    title: str
    status: str
    last_message_at: Optional[datetime] = None
