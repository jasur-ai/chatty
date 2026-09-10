"""Cloudflare R2 (S3-compatible) media storage."""
import uuid
from typing import BinaryIO

import boto3
from botocore.client import Config

from .config import settings


class R2Storage:
    def __init__(self) -> None:
        self.enabled = settings.r2_enabled
        if not self.enabled:
            return
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
        self.bucket = settings.r2_bucket

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, data: bytes, content_type: str, ext: str = "") -> str:
        """Faylni yuklaydi va R2 key qaytaradi."""
        if not self.enabled:
            return ""
        self._ensure_bucket()
        key = f"media/{uuid.uuid4().hex}{ext}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return key

    def url(self, key: str) -> str:
        if settings.r2_public_url:
            return f"{settings.r2_public_url.rstrip('/')}/{key}"
        return f"/api/media/{key}"

    def get(self, key: str) -> bytes:
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()


storage = R2Storage()