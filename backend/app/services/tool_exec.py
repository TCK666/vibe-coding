"""工具集执行器。里程碑5实现 db_query（只读）；其余工具里程碑6接入。"""
import json
import re

from sqlalchemy import text

from ..core.errors import BizError
from ..db.session import engine

MAX_FULL_OUTPUT = 4000
MAX_SUMMARY = 500

FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|attach|detach|pragma|grant|revoke)\b",
    re.IGNORECASE,
)

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
    }
]


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


async def execute_tool(name: str, arguments_json: str) -> tuple[str, str]:
    """执行工具，返回 (summary≤500字, full_output)。失败时抛 BizError，由调用方转为失败摘要。"""
    if name != "db_query":
        raise BizError("TOOL_NOT_IMPLEMENTED", f"工具 {name} 将在里程碑6接入", 400)

    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError:
        raise BizError("TOOL_ARGS_INVALID", "工具参数不是合法 JSON", 400)
    sql = _validate_select(str(args.get("sql", "")))

    async with engine.connect() as conn:
        result = await conn.execute(text(sql))
        rows = [dict(r._mapping) for r in result.fetchmany(100)]

    for row in rows:  # 序列化兼容（datetime/Decimal 等）
        for k, v in row.items():
            if not isinstance(v, (str, int, float, bool)) and v is not None:
                row[k] = str(v)

    full = json.dumps(rows, ensure_ascii=False)
    if len(full) > MAX_FULL_OUTPUT:
        full = full[:MAX_FULL_OUTPUT] + "...(截断)"
    preview = json.dumps(rows[0], ensure_ascii=False)[:120] if rows else "无数据"
    summary = f"db_query 成功，返回 {len(rows)} 行；首行: {preview}"
    return summary[:MAX_SUMMARY], full
