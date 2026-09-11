"""Media storage — Cloudflare R2 (S3-compatible) + lokal disk fallback.

R2 sozlanmagan yoki ishlamasa, fayllar lokal disk'da (data/media) saqlanadi —
shuning uchun media/rasmlar R2 aktivlashtirilmaganda ham ishlaydi.

Muhim: R2 aloqa xatosi (SSL/timeout) bo'lsa "circuit breaker" ishga tushadi —
qolgan jarayon davomida R2'ni o'chiradi va lokal disk'ga DARHOL tushadi.
Aks holda har bir R2 so'rovi 10–40 soniya qayta urinishda kuyib ketardi.
"""
import logging
import mimetypes
import uuid
from pathlib import Path

from .config import settings

logger = logging.getLogger("chatty.storage")

_LOCAL_DIR = Path("data/media")

# content-type xaritasi (lokal fallback uchun)
_CT = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
    ".gif": "image/gif", ".mp4": "video/mp4", ".mov": "video/quicktime",
    ".ogg": "audio/ogg", ".opus": "audio/ogg", ".mp3": "audio/mpeg", ".m4a": "audio/mp4",
    ".webm": "video/webm", ".pdf": "application/pdf", ".txt": "text/plain",
    ".zip": "application/zip", ".doc": "application/msword", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _guess_ct(key: str) -> str:
    ext = Path(key).suffix.lower()
    return _CT.get(ext, mimetypes.guess_type(key)[0] or "application/octet-stream")


class R2Storage:
    def __init__(self) -> None:
        self.enabled = settings.r2_enabled
        self.client = None
        self.bucket = settings.r2_bucket
        self._bucket_ok = False
        self._broken = False
        _LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        if self.enabled:
            try:
                import boto3
                from botocore.client import Config

                self.client = boto3.client(
                    "s3",
                    endpoint_url=settings.r2_endpoint,
                    aws_access_key_id=settings.r2_access_key_id,
                    aws_secret_access_key=settings.r2_secret_access_key,
                    # Tez muvaffaqiyatsizlik: qisqa timeout, kam qayta urinish —
                    # R2 ishlamasa darhol lokal disk'ga tushamiz.
                    config=Config(
                        signature_version="s3v4",
                        retries={"max_attempts": 1, "mode": "standard"},
                        connect_timeout=5,
                        read_timeout=15,
                    ),
                    region_name="auto",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("R2 client yaratilmadi: %s", exc)
                self.client = None

    # -- circuit breaker -----------------------------------------------------
    def _mark_broken(self, exc: Exception) -> None:
        """Aloqa xatosi bo'lsa R2'ni jarayon davomida o'chirib qo'yamiz."""
        if self._broken:
            return
        self._broken = True
        self.client = None
        logger.warning("R2 aloqa xatosi — lokal disk'ga o'tildi: %s", exc)

    @staticmethod
    def _is_connect_error(exc: Exception) -> bool:
        """Bu xato R2'ning o'zi emas, balki aloqa (SSL/timeout/DNS) muammosi."""
        try:
            from botocore.exceptions import ClientError, EndpointConnectionError

            if isinstance(exc, EndpointConnectionError):
                return True
            if isinstance(exc, ClientError):
                code = getattr(exc, "response", {}).get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
                # 4xx = R2 ishlayapti (Not Found/Access Denied) — aloqa xatosi emas.
                return code >= 500
        except Exception:  # noqa: BLE001
            pass
        name = type(exc).__name__.lower()
        return any(t in name for t in ("ssl", "timeout", "connection", "socket", "read", "connect", "urlerror"))

    def _ok(self) -> bool:
        return self.client is not None and not self._broken

    # -- operations ----------------------------------------------------------
    def _ensure_bucket(self) -> None:
        if not self._ok() or self._bucket_ok:
            return
        try:
            self.client.head_bucket(Bucket=self.bucket)
            self._bucket_ok = True
        except Exception as exc:  # noqa: BLE001
            if self._is_connect_error(exc):
                self._mark_broken(exc)
            else:
                try:
                    self.client.create_bucket(Bucket=self.bucket)
                    self._bucket_ok = True
                except Exception as exc2:  # noqa: BLE001
                    if self._is_connect_error(exc2):
                        self._mark_broken(exc2)

    def put(self, data: bytes, content_type: str, ext: str = "") -> str:
        """Faylni saqlaydi va key qaytaradi (R2 yoki lokal)."""
        key = f"media/{uuid.uuid4().hex}{ext}"
        if self._ok():
            try:
                self._ensure_bucket()
                if self._ok():
                    self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
                    return key
            except Exception as exc:  # noqa: BLE001
                if self._is_connect_error(exc):
                    self._mark_broken(exc)
                else:
                    logger.warning("R2 put xatosi: %s", exc)
        # Lokal fallback
        path = _LOCAL_DIR / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def url(self, key: str) -> str:
        if not key:
            return ""
        if settings.r2_public_url:
            return f"{settings.r2_public_url.rstrip('/')}/{key}"
        return f"/api/media/{key}"

    def exists(self, key: str) -> bool:
        """Fayl mavjudligini tekshiradi.

        R2 (S3) doimiy saqlash — media_key yozilgandan keyin fayl o'chmaydi,
        shuning uchun har bir xabar uchun tarmoq so'rovi (head_object) qilmaymiz.
        Lokal disk (Render ephemeral) uchun esa haqiqiy faylni tekshiramiz,
        chunki redeploy'da fayllar o'chib ketishi mumkin.
        """
        if not key:
            return False
        if self._ok():
            return True
        return (_LOCAL_DIR / key).exists()

    def get(self, key: str) -> tuple[bytes, str]:
        """Faylni va content-type'ini qaytaradi."""
        if self._ok():
            try:
                obj = self.client.get_object(Bucket=self.bucket, Key=key)
                return obj["Body"].read(), obj.get("ContentType", "application/octet-stream")
            except Exception as exc:  # noqa: BLE001
                if self._is_connect_error(exc):
                    self._mark_broken(exc)
                else:
                    logger.warning("R2 get xatosi: %s", exc)
        path = _LOCAL_DIR / key
        if path.exists():
            return path.read_bytes(), _guess_ct(key)
        raise FileNotFoundError(key)


storage = R2Storage()
