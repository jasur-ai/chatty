"""JWT (web app auth) va Fernet (StringSession shifrlash)."""
import base64
import hashlib
import hmac
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

# ---------- Media URL imzolash (HMAC) ----------
# <img>/<audio>/<video> teglari Authorization sarlavhasini yubora olmaydi.
# Shu sababli media endpointlari URL'ga joylangan qisqa muddatli HMAC imzo
# bilan himoyalanadi — aks holda ketma-ket id'larni sanash (IDOR) orqali
# har kim begonalar yuborgan maxfiy rasm/ovoz/videolarni yuklab olishi mumkin.
_MEDIA_TTL_SECONDS = 12 * 3600  # 12 soat


def _media_sig(path: str, exp: int | str) -> str:
    payload = f"{path}:{exp}".encode()
    return hmac.new(settings.jwt_secret.encode(), payload, hashlib.sha256).hexdigest()[:32]


def sign_media_url(path: str, ttl_seconds: int = _MEDIA_TTL_SECONDS) -> str:
    """Media path'ga imzolangan `?e=<expiry>&s=<signature>` qo'shadi."""
    exp = int((datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).timestamp())
    return f"{path}?e={exp}&s={_media_sig(path, exp)}"


def verify_media_url(path: str, exp: str | None, sig: str | None) -> bool:
    """Imzo to'g'ri va muddati tugamaganmi?"""
    if not exp or not sig:
        return False
    try:
        exp_int = int(exp)
    except (TypeError, ValueError):
        return False
    if exp_int < int(datetime.now(timezone.utc).timestamp()):
        return False
    return hmac.compare_digest(_media_sig(path, exp_int), sig)
