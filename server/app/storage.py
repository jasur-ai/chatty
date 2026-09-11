"""Media storage — Cloudflare R2 (S3-compatible) + lokal disk fallback.

R2 sozlanmagan yoki ishlamasa, fayllar lokal disk'da (data/media) saqlanadi —
shuning uchun media/rasmlar R2 aktivlashtirilmaganda ham ishlaydi.
"""
import mimetypes
import uuid
from pathlib import Path

from .config import settings

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
                    config=Config(signature_version="s3v4"),
                    region_name="auto",
                )
            except Exception:
                self.client = None

    def _ensure_bucket(self) -> None:
        if not self.client:
            return
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self.client.create_bucket(Bucket=self.bucket)
            except Exception:
                pass

    def put(self, data: bytes, content_type: str, ext: str = "") -> str:
        """Faylni saqlaydi va key qaytaradi (R2 yoki lokal)."""
        key = f"media/{uuid.uuid4().hex}{ext}"
        if self.client:
            try:
                self._ensure_bucket()
                self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
                return key
            except Exception:
                pass  # R2 ishlamasa lokal'ga tushamiz
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
        """Fayl hali ham saqlanayotganini tekshiradi (lokal yoki R2)."""
        if not key:
            return False
        if self.client:
            try:
                self.client.head_object(Bucket=self.bucket, Key=key)
                return True
            except Exception:
                pass
        return (_LOCAL_DIR / key).exists()

    def get(self, key: str) -> tuple[bytes, str]:
        """Faylni va content-type'ini qaytaradi."""
        if self.client:
            try:
                obj = self.client.get_object(Bucket=self.bucket, Key=key)
                return obj["Body"].read(), obj.get("ContentType", "application/octet-stream")
            except Exception:
                pass
        path = _LOCAL_DIR / key
        if path.exists():
            return path.read_bytes(), _guess_ct(key)
        raise FileNotFoundError(key)


storage = R2Storage()
