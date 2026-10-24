"""长连接模块：一次性 ws-token 签发 + 会话级 WS 通道（里程碑5实现）。"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..core.errors import BizError, ok
from ..db.session import SessionLocal, get_db
from ..models import Conversation, User, WebsocketToken
from ..services import task_engine
from ..services.ws_manager import ws_manager

router = APIRouter(prefix="/api/chat", tags=["ws"])

WS_TOKEN_TTL_SECONDS = 30


class WsTokenReq(BaseModel):
    conversation_id: int


@router.post("/ws-token", summary="签发一次性 WebSocket 连接令牌")
async def create_ws_token(
    req: WsTokenReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = (
        await db.execute(
            select(Conversation).where(
                Conversation.id == req.conversation_id, Conversation.user_id == user.id
            )
        )
    ).scalar_one_or_none()
    if conv is None:
        raise BizError("CONV_NOT_FOUND", "会话不存在", 404)

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(seconds=WS_TOKEN_TTL_SECONDS)
    db.add(
        WebsocketToken(
            user_id=user.id, conversation_id=conv.id, token=token, expires_at=expires_at
        )
    )
    await db.commit()
    return ok({"websocket_token": token, "expires_in": WS_TOKEN_TTL_SECONDS})


async def _consume_ws_token(
    db: AsyncSession, token: str, conversation_id: int
) -> int | None:
    """校验并消费一次性 WS 令牌：合法返回属主 user_id，否则 None。"""
    row = (
        await db.execute(select(WebsocketToken).where(WebsocketToken.token == token))
    ).scalar_one_or_none()
    if (
        row is None
        or row.conversation_id != conversation_id
        or row.consumed_at is not None
        or row.expires_at <= datetime.now()
    ):
        return None
    row.consumed_at = datetime.now()
    await db.commit()
    return row.user_id


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket, websocket_token: str = "", conversation_id: int = 0):
    """会话级实时通道。鉴权用一次性 token；消息协议见 spec §1/§3。"""
    await websocket.accept()
    async with SessionLocal() as db:
        user_id = await _consume_ws_token(db, websocket_token, conversation_id)
    if user_id is None:
        await websocket.close(code=4401, reason="invalid websocket token")
        return

    await ws_manager.connect(conversation_id, websocket)
    try:
        while True:
            try:
                msg = await websocket.receive_json()
            except Exception:
                break  # 非JSON帧或断开
            mtype = msg.get("type")
            if mtype == "chat":
                content = str(msg.get("content", "")).strip()
                if not content:
                    await ws_manager.broadcast(
                        conversation_id, "error",
                        {"task_id": None, "error_message": "消息内容不能为空"},
                    )
                    continue
                try:
                    await task_engine.start_task(conversation_id, user_id, content)
                except BizError as e:
                    await ws_manager.broadcast(
                        conversation_id,
                        "error",
                        {"task_id": None, "error_message": f"{e.code}: {e.message}"},
                    )
            elif mtype == "cancel":
                try:
                    await task_engine.cancel_task(int(msg.get("task_id", 0)), user_id)
                except (BizError, ValueError) as e:
                    reason = e.message if isinstance(e, BizError) else str(e)
                    await ws_manager.broadcast(
                        conversation_id, "error",
                        {"task_id": msg.get("task_id"), "error_message": reason},
                    )
            elif mtype == "ping":
                async with ws_manager._lock(conversation_id):
                    await ws_manager._send(websocket, {"type": "pong", "data": {}, "ts": 0})
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(conversation_id, websocket)
