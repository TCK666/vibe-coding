"""通用出入参模型。业务模块的 schema 在各自里程碑补充。"""
from typing import Any

from pydantic import BaseModel


class ApiResponse(BaseModel):
    code: int | str = 0
    message: str = "ok"
    data: Any = None
