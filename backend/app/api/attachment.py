"""附件模块接口（里程碑4实现：上传/删除/下载/列表）。"""
from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..core.errors import BizError, ok
from ..db.session import get_db
from ..models import User
from ..schemas.chat import DeleteAttachmentReq
from ..services import attachment_service, conversation_service

router = APIRouter(prefix="/api/attachment", tags=["attachment"])


@router.post("/upload", summary="上传附件")
async def upload_attachment(
    conversation_id: int = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await conversation_service.get_owned_conversation(db, conversation_id, user.id)
    att = await attachment_service.save_upload(db, conversation_id, user.id, file)
    return ok(
        {
            "attachment_id": att.id,
            "file_name": att.file_name,
            "file_path": att.file_path,
        }
    )


@router.post("/delete", summary="删除附件")
async def delete_attachment(
    req: DeleteAttachmentReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    att = await attachment_service.get_owned_attachment(db, req.attachment_id, user.id)
    await attachment_service.delete_attachment(db, att)
    return ok({"attachment_id": req.attachment_id})


@router.get("/get", summary="下载附件")
async def get_attachment(
    attachment_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    att = await attachment_service.get_owned_attachment(db, attachment_id, user.id)
    abs_path = attachment_service.attachment_abs_path(att)
    if not abs_path.is_file():
        raise BizError("ATTACHMENT_FILE_MISSING", "附件文件已丢失", 404)
    return FileResponse(abs_path, filename=att.file_name)


@router.get("/ls", summary="会话附件列表")
async def list_attachments(
    conversation_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await conversation_service.get_owned_conversation(db, conversation_id, user.id)
    atts = await attachment_service.list_attachments(db, conversation_id)
    return ok(
        {
            "attachments": [
                {
                    "attachment_id": a.id,
                    "file_name": a.file_name,
                    "file_type": a.file_type,
                    "file_size": a.file_size,
                    "parse_status": a.parse_status,
                    "created_at": a.created_at,
                }
                for a in atts
            ]
        }
    )
