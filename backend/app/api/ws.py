"""长连接模块接口骨架（里程碑5实现：ws-token 签发 + WS 会话通道）。"""
from fastapi import APIRouter

from ..core.errors import BizError

router = APIRouter(prefix="/api/chat", tags=["ws"])


@router.post("/ws-token", summary="签发一次性 WebSocket 连接令牌")
async def create_ws_token():
    raise BizError("NOT_IMPLEMENTED", "长连接接口在里程碑5实现", 501)
