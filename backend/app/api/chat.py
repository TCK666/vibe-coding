"""会话模块接口骨架（里程碑4实现：会话CRUD、消息查询、删除级联）。"""
from fastapi import APIRouter

from ..core.errors import BizError

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/create", summary="创建会话")
async def create_conversation():
    raise BizError("NOT_IMPLEMENTED", "会话接口在里程碑4实现", 501)


@router.post("/delete", summary="删除会话（级联删除消息/附件/任务/结果/摘要与文件目录）")
async def delete_conversations():
    raise BizError("NOT_IMPLEMENTED", "会话接口在里程碑4实现", 501)


@router.post("/update", summary="重命名会话")
async def update_conversation():
    raise BizError("NOT_IMPLEMENTED", "会话接口在里程碑4实现", 501)


@router.get("/ls", summary="会话列表")
async def list_conversations():
    raise BizError("NOT_IMPLEMENTED", "会话接口在里程碑4实现", 501)


@router.get("/ls/{conversation_id}", summary="历史消息")
async def list_messages(conversation_id: int):
    raise BizError("NOT_IMPLEMENTED", "会话接口在里程碑4实现", 501)
