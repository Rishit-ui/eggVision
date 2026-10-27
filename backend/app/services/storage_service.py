"""Image artifact storage with S3-compatible RustFS support and local development fallback."""

import asyncio
import logging
import os
from pathlib import Path

import aiofiles
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        self.upload_dir = Path(__file__).resolve().parents[2] / "uploads"
        self.upload_dir.mkdir(exist_ok=True)
        self._s3_configured = all(
            (settings.S3_ENDPOINT, settings.S3_BUCKET, settings.S3_ACCESS_KEY, settings.S3_SECRET_KEY)
        )
        self._s3_available = False
        self._client = None
        if self._s3_configured:
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
                region_name="us-east-1",
                config=Config(signature_version="s3v4"),
            )

    @property
    def uses_s3(self) -> bool:
        return self._s3_available

    @staticmethod
    def _safe_key(filename: str) -> str:
        """Allow only server-generated single filename keys."""
        key = Path(filename).name
        if not key or key != filename or key in {".", ".."}:
            raise ValueError("Invalid storage object name")
        return key

    async def ensure_ready(self) -> None:
        """Create or verify the configured bucket before the API accepts uploads."""
        if not self._s3_configured:
            return

        def ensure_bucket() -> None:
            assert self._client is not None
            assert settings.S3_BUCKET is not None
            try:
                self._client.head_bucket(Bucket=settings.S3_BUCKET)
            except ClientError as error:
                code = str(error.response.get("Error", {}).get("Code", ""))
                if code not in {"404", "NoSuchBucket"}:
                    raise
                self._client.create_bucket(Bucket=settings.S3_BUCKET)

        try:
            await asyncio.to_thread(ensure_bucket)
            self._s3_available = True
        except Exception:
            self._s3_available = False
            if settings.S3_REQUIRED:
                raise
            logger.warning("S3-compatible storage is unavailable; using local development artifact storage")

    async def upload_image(self, file_data: bytes, filename: str, content_type: str) -> str:
        key = self._safe_key(filename)
        if self._s3_available:
            assert self._client is not None and settings.S3_BUCKET is not None
            await asyncio.to_thread(
                self._client.put_object,
                Bucket=settings.S3_BUCKET,
                Key=key,
                Body=file_data,
                ContentType=content_type,
            )
            return f"/api/v1/artifacts/{key}"

        path = self.upload_dir / key
        async with aiofiles.open(path, "wb") as file:
            await file.write(file_data)
        return f"/uploads/{key}"

    async def get_image(self, filename: str) -> tuple[bytes, str]:
        key = self._safe_key(filename)
        if self._s3_available:
            assert self._client is not None and settings.S3_BUCKET is not None

            def get_s3() -> tuple[bytes, str]:
                response = self._client.get_object(Bucket=settings.S3_BUCKET, Key=key)
                return response["Body"].read(), response.get("ContentType", "application/octet-stream")

            return await asyncio.to_thread(get_s3)

        path = self.upload_dir / key
        if not path.is_file():
            raise FileNotFoundError(key)
        async with aiofiles.open(path, "rb") as file:
            return await file.read(), "application/octet-stream"

    async def delete_image(self, filename: str) -> bool:
        key = self._safe_key(filename)
        if self._s3_available:
            assert self._client is not None and settings.S3_BUCKET is not None
            await asyncio.to_thread(self._client.delete_object, Bucket=settings.S3_BUCKET, Key=key)
            return True
        path = self.upload_dir / key
        if not path.is_file():
            return False
        path.unlink()
        return True

    async def health_status(self) -> str:
        if self._s3_configured:
            if self._s3_available:
                return "ok"
            return "degraded" if os.access(self.upload_dir, os.W_OK) else "error"
        return "ok" if os.access(self.upload_dir, os.W_OK) else "error"

storage_service = StorageService()
