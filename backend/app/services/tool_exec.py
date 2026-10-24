"""工具集执行器：db_query / file_read / file_write / text_search / cmd_exec。

安全边界（概要设计 §6.5）：SQL 只读白名单；文件读写 resolve 后必须位于会话
workspace 目录；命令首词白名单 + 超时 + 目录隔离。
"""
import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.pool import NullPool

from ..core.errors import BizError
from ..tools import _paths

MAX_FULL_OUTPUT = 4000
MAX_SUMMARY = 500
MAX_WRITE_SIZE = 100 * 1024
CMD_TIMEOUT = 30
DEFAULT_CMD_WHITELIST = "python,ping,dir"

FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|attach|detach|pragma|grant|revoke)\b",
    re.IGNORECASE,
)


@dataclass
class ToolContext:
    user_id: int
    conversation_id: int

    @property
    def workspace_dir(self) -> Path:
        d = _paths.WORKSPACE_ROOT / str(self.user_id) / str(self.conversation_id)
        d.mkdir(parents=True, exist_ok=True)
        return d


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "db_query",
            "description": "对业务数据表执行只读 SELECT 查询，返回 JSON 行数据。用于获取指标、证据。",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "单条只读 SELECT 语句"}},
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "读取会话工作目录内的文本文件（含附件解析文本 parsed_*.txt）。",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "工作目录内相对路径"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "向会话工作目录写入文本文件（如中间统计结果）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "工作目录内相对路径"},
                    "content": {"type": "string", "description": "文本内容"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "text_search",
            "description": "在会话工作目录与附件解析文本中按关键词逐行检索。",
            "parameters": {
                "type": "object",
                "properties": {"keyword": {"type": "string", "description": "关键词"}},
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cmd_exec",
            "description": "在工作目录内执行受限命令（白名单，如 python 统计脚本），返回输出。",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "命令行"}},
                "required": ["command"],
            },
        },
    },
]


async def _get_config(key: str, default: str) -> str:
    from .config_service import get_sync

    return get_sync(key, default)


def _validate_select(sql: str) -> str:
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql.lower().startswith("select"):
        raise BizError("TOOL_SQL_INVALID", "仅允许 SELECT 查询", 400)
    if ";" in sql:
        raise BizError("TOOL_SQL_INVALID", "仅允许单条语句", 400)
    if FORBIDDEN_KEYWORDS.search(sql):
        raise BizError("TOOL_SQL_INVALID", "语句包含被禁止的关键字", 400)
    if not re.search(r"\blimit\b", sql, re.IGNORECASE):
        sql += " LIMIT 100"
    return sql


def _truncate(s: str, limit: int = MAX_FULL_OUTPUT) -> str:
    return s if len(s) <= limit else s[:limit] + "...(截断)"


def _ws_file(ctx: ToolContext, rel: str) -> Path:
    if not rel or Path(rel).is_absolute():
        raise BizError("TOOL_PATH_INVALID", "必须是工作目录内相对路径", 400)
    return _paths.ensure_under(ctx.workspace_dir, ctx.workspace_dir / rel)


_query_engines = {}  # dsn -> AsyncEngine（readonly_dsn 数据源缓存）


async def _query_engine():
    """db_query 的数据源：tool.db_query.readonly_dsn 非空则用独立连接，否则应用库。"""
    from sqlalchemy.ext.asyncio import create_async_engine

    from ..db.session import engine

    dsn = (await _get_config("tool.db_query.readonly_dsn", "")).strip()
    if not dsn:
        return engine
    if dsn not in _query_engines:
        kwargs = {"poolclass": NullPool} if dsn.startswith("sqlite") else {}
        _query_engines[dsn] = create_async_engine(dsn, **kwargs)
    return _query_engines[dsn]


async def _tool_db_query(ctx: ToolContext, args: dict) -> tuple[str, str]:
    eng = await _query_engine()
    sql = _validate_select(str(args.get("sql", "")))
    async with eng.connect() as conn:
        result = await conn.execute(text(sql))
        rows = [dict(r._mapping) for r in result.fetchmany(100)]
    for row in rows:
        for k, v in row.items():
            if not isinstance(v, (str, int, float, bool)) and v is not None:
                row[k] = str(v)
    full = _truncate(json.dumps(rows, ensure_ascii=False))
    preview = json.dumps(rows[0], ensure_ascii=False)[:120] if rows else "无数据"
    return f"db_query 成功，返回 {len(rows)} 行；首行: {preview}", full


async def _tool_file_read(ctx: ToolContext, args: dict) -> tuple[str, str]:
    p = _ws_file(ctx, str(args.get("path", "")))
    if not p.is_file():
        raise BizError("TOOL_FILE_MISSING", f"文件不存在: {args.get('path')}", 404)
    content = p.read_text(encoding="utf-8", errors="replace")
    return f"file_read 成功，{len(content)} 字符", _truncate(content)


async def _tool_file_write(ctx: ToolContext, args: dict) -> tuple[str, str]:
    p = _ws_file(ctx, str(args.get("path", "")))
    content = str(args.get("content", ""))
    if len(content.encode("utf-8")) > MAX_WRITE_SIZE:
        raise BizError("TOOL_WRITE_TOO_LARGE", "写入内容超过 100KB", 400)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"file_write 成功，写入 {args.get('path')}（{len(content)} 字符）", "ok"


async def _tool_text_search(ctx: ToolContext, args: dict) -> tuple[str, str]:
    keyword = str(args.get("keyword", "")).strip()
    if not keyword:
        raise BizError("TOOL_ARGS_INVALID", "keyword 不能为空", 400)
    hits: list[str] = []
    for f in sorted(ctx.workspace_dir.rglob("*")):
        if not f.is_file():
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        rel = f.relative_to(ctx.workspace_dir).as_posix()
        for no, line in enumerate(lines, 1):
            if keyword.lower() in line.lower():
                hits.append(f"{rel}:{no}: {line.strip()[:200]}")
                if len(hits) >= 20:
                    break
        if len(hits) >= 20:
            break
    full = "\n".join(hits) if hits else f"未命中关键词: {keyword}"
    return f"text_search 命中 {len(hits)} 条", _truncate(full)


async def _tool_cmd_exec(ctx: ToolContext, args: dict) -> tuple[str, str]:
    command = str(args.get("command", "")).strip()
    if not command:
        raise BizError("TOOL_ARGS_INVALID", "command 不能为空", 400)
    whitelist = [w.strip().lower() for w in (await _get_config("tool.cmd.whitelist", DEFAULT_CMD_WHITELIST)).split(",") if w.strip()]
    first = Path(command.split()[0]).stem.lower() if command.split() else ""
    if first not in whitelist:
        raise BizError("TOOL_CMD_FORBIDDEN", f"命令不在白名单: {first}", 400)
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(ctx.workspace_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=CMD_TIMEOUT)
    except asyncio.TimeoutError:
        raise BizError("TOOL_CMD_TIMEOUT", f"命令执行超过 {CMD_TIMEOUT}s 被终止", 400)
    output = (out.decode("utf-8", errors="replace") + ("\n" + err.decode("utf-8", errors="replace") if err else "")).strip()
    status = "成功" if proc.returncode == 0 else f"退出码 {proc.returncode}"
    return f"cmd_exec {status}，输出 {len(output)} 字符", _truncate(output)


_TOOLS = {
    "db_query": _tool_db_query,
    "file_read": _tool_file_read,
    "file_write": _tool_file_write,
    "text_search": _tool_text_search,
    "cmd_exec": _tool_cmd_exec,
}


async def execute_tool(name: str, arguments_json: str, ctx: ToolContext) -> tuple[str, str]:
    """执行工具，返回 (summary≤500字, full_output)。失败抛 BizError，由调用方转为失败摘要。"""
    fn = _TOOLS.get(name)
    if fn is None:
        raise BizError("TOOL_NOT_IMPLEMENTED", f"未知工具: {name}", 400)
    try:
        args = json.loads(arguments_json or "{}")
        if not isinstance(args, dict):
            raise ValueError
    except json.JSONDecodeError:
        raise BizError("TOOL_ARGS_INVALID", "工具参数不是合法 JSON", 400)
    except ValueError:
        raise BizError("TOOL_ARGS_INVALID", "工具参数必须是 JSON 对象", 400)
    return await fn(ctx, args)
