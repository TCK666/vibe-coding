"""附件服务：保存、解析、下载路径解析、删除，含越界校验。"""
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import BizError
from ..models import Attachment, Conversation
from ..tools import _paths

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MAX_PARSE_SIZE = 200 * 1024  # 解析文本上限 200KB
TEXT_SUFFIXES = {"txt", "md", "csv", "json", "log", "py", "sql", "html", "htm", "tsv"}


def parsed_text_path(user_id: int, conversation_id: int, attachment_id: int) -> Path:
    d = _paths.WORKSPACE_ROOT / str(user_id) / str(conversation_id)
    d.mkdir(parents=True, exist_ok=True)
    return d / f"parsed_{attachment_id}.txt"


async def parse_and_store(att: Attachment, user_id: int) -> bool:
    """上传后同步解析：文本类文件抽取文本写 workspace/parsed_{id}.txt，成功返回 True。"""
    try:
        abs_path = attachment_abs_path(att)
        suffix = (att.file_type or "").lower().lstrip(".")
        if suffix not in TEXT_SUFFIXES or not abs_path.is_file():
            return False
        raw = abs_path.read_bytes()[:MAX_PARSE_SIZE]
        text = raw.decode("utf-8", errors="replace")
        out = parsed_text_path(user_id, att.conversation_id, att.id)
        out.write_text(text, encoding="utf-8")
        return True
    except Exception:
        return False


def safe_filename(name: str) -> str:
    """去掉路径成分与控制字符，保留原始文件名。"""
    name = Path(name or "file").name
    return name.replace("\x00", "").strip() or "file"


async def save_upload(
    db: AsyncSession, conversation_id: int, user_id: int, upload: UploadFile
) -> Attachment:
    rel_dir = Path("uploads") / str(user_id) / str(conversation_id)
    abs_dir = _paths.UPLOADS_ROOT / str(user_id) / str(conversation_id)
    abs_dir.mkdir(parents=True, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_filename(upload.filename or 'file')}"
    abs_path = abs_dir / unique_name

    size = 0
    with open(abs_path, "wb") as f:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                f.close()
                abs_path.unlink(missing_ok=True)
                raise BizError("FILE_TOO_LARGE", "附件不能超过 50MB", 400)
            f.write(chunk)

    att = Attachment(
        conversation_id=conversation_id,
        file_name=safe_filename(upload.filename or "file"),
        file_path=rel_dir.as_posix() + "/" + unique_name,
        file_type=Path(upload.filename or "").suffix.lower().lstrip("."),
        file_size=size,
        parse_status="pending",
    )
    db.add(att)
    await db.commit()
    await db.refresh(att)
    return att


async def list_attachments(db: AsyncSession, conversation_id: int) -> list[Attachment]:
    result = await db.execute(
        select(Attachment)
        .where(Attachment.conversation_id == conversation_id)
        .order_by(Attachment.id)
    )
    return list(result.scalars().all())


async def get_owned_attachment(db: AsyncSession, attachment_id: int, user_id: int) -> Attachment:
    """附件归属 = 附件所属会话属于该用户，否则一律 404（不泄露存在性）。"""
    att = (
        await db.execute(select(Attachment).where(Attachment.id == attachment_id))
    ).scalar_one_or_none()
    if att is not None:
        conv = (
            await db.execute(select(Conversation).where(Conversation.id == att.conversation_id))
        ).scalar_one_or_none()
        if conv is not None and conv.user_id == user_id:
            return att
    raise BizError("ATTACHMENT_NOT_FOUND", "附件不存在", 404)


def attachment_abs_path(att: Attachment) -> Path:
    """带前缀的 file_path（uploads/{u}/{c}/{name}）→ 越界校验后的绝对路径。"""
    return _paths.resolve_stored_path(att.file_path)


async def delete_attachment(db: AsyncSession, att: Attachment) -> None:
    abs_path = attachment_abs_path(att)  # 先校验，再删记录与文件
    await db.delete(att)
    await db.commit()
    abs_path.unlink(missing_ok=True)
