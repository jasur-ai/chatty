"""JWT (web app auth) va Fernet (StringSession shifrlash)."""
import base64
import hashlib
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken

from .config import settings

_ALGO = "HS256"
_TOKEN_TTL = timedelta(days=30)


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.session_secret.encode()).digest())
    return Fernet(key)


# ---------- JWT ----------
def create_token(account_id: int) -> str:
    payload = {
        "sub": str(account_id),
        "exp": datetime.now(timezone.utc) + _TOKEN_TTL,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGO)


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_ALGO])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


# ---------- StringSession shifrlash ----------
def encrypt_session(raw: str) -> str:
    return _fernet().encrypt(raw.encode()).decode()


def decrypt_session(enc: str) -> str | None:
    if not enc:
        return None
    try:
        return _fernet().decrypt(enc.encode()).decode()
    except InvalidToken:
        return None