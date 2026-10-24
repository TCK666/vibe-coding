"""JWT 签发与校验（本系统登录态，与认证中心令牌分离）。"""
import time

from jose import JWTError, jwt

from .config import get_settings
from .errors import BizError


def create_access_token(user_id: int, external_user_id: str, role: str) -> tuple[str, int]:
    s = get_settings()
    expires_in = s.jwt_expires_min * 60
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "uid": external_user_id,
        "role": role,
        "iat": now,
        "exp": now + expires_in,
    }
    token = jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_alg)
    return token, expires_in


def decode_access_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_alg])
    except JWTError:
        raise BizError("AUTH_TOKEN_INVALID", "访问令牌无效或已过期", 401)
