"""附件模块接口骨架（里程碑4实现：上传/删除/下载，路径校验）。"""
from fastapi import APIRouter

from ..core.errors import BizError

router = APIRouter(prefix="/api/attachment", tags=["attachment"])


@router.post("/upload", summary="上传附件")
async def upload_attachment():
    raise BizError("NOT_IMPLEMENTED", "附件接口在里程碑4实现", 501)


@router.post("/delete", summary="删除附件")
async def delete_attachment():
    raise BizError("NOT_IMPLEMENTED", "附件接口在里程碑4实现", 501)


@router.get("/get", summary="下载附件")
async def get_attachment():
    raise BizError("NOT_IMPLEMENTED", "附件接口在里程碑4实现", 501)
