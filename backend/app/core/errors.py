"""统一响应包与业务异常。

成功: {"code": 0, "message": "ok", "data": ...}
失败: {"code": "AUTH_XXX", "message": "...", "data": null}
"""
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("baas")


class BizError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(message)


def ok(data=None):
    return {"code": 0, "message": "ok", "data": data}


async def biz_error_handler(request: Request, exc: BizError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("未处理异常 %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": "服务内部错误", "data": None},
    )
