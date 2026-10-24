"""文件存储根路径与越界校验（概要设计 §7.3 / §12）。

目录约定（相对 backend/，file_path 一律正斜杠）：
  uploads/{user_id}/{conversation_id}/    附件
  exports/{user_id}/{conversation_id}/    导出结果
  workspace/{user_id}/{conversation_id}/  分析中间文件
"""
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
UPLOADS_ROOT = BACKEND_ROOT / "uploads"
EXPORTS_ROOT = BACKEND_ROOT / "exports"
WORKSPACE_ROOT = BACKEND_ROOT / "workspace"


def ensure_under(root: Path, target: Path) -> Path:
    """校验 target 解析后必须位于 root 内，返回解析后的绝对路径；越界抛 BizError。"""
    from ..core.errors import BizError

    resolved_root = root.resolve()
    resolved = target.resolve()
    if resolved != resolved_root and not resolved.is_relative_to(resolved_root):
        raise BizError("FILE_PATH_INVALID", "文件路径非法", 400)
    return resolved


def abs_from_rel(rel_path: str, root: Path) -> Path:
    """相对 file_path → 绝对路径并做越界校验。"""
    return ensure_under(root, Path(root) / rel_path)


# 存储路径前缀 → 物理根目录。file_path 约定形如 "uploads/{u}/{c}/{name}"
_ROOTS = {
    "uploads": UPLOADS_ROOT,
    "exports": EXPORTS_ROOT,
    "workspace": WORKSPACE_ROOT,
}


def resolve_stored_path(rel_path: str) -> Path:
    """按前缀选择根目录，解析出绝对路径并做越界校验。"""
    from ..core.errors import BizError

    parts = Path(rel_path).parts
    if not parts or parts[0] not in _ROOTS:
        raise BizError("FILE_PATH_INVALID", "文件路径非法", 400)
    root = _ROOTS[parts[0]]
    return ensure_under(root, root.joinpath(*parts[1:]))
