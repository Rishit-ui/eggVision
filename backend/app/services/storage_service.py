"""
Image artifact storage — S3-compatible backend (Supabase Storage) with
a local development fallback.

Production Supabase S3 notes:
  endpoint_url : https://<project>.supabase.co/storage/v1/s3
  region       : us-east-1 (always, even for projects in other regions)
  bucket       : set via env S3_BUCKET (create it in the Supabase dashboard first)
  credentials  : S3_ACCESS_KEY = project access-key id
                 S3_SECRET_KEY = project secret-access-key
"""

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
    def __init__(self) -> None:
        self.upload_dir = Path(__file__).resolve().parents[2] / "uploads"
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass  # /tmp or read-only filesystem in serverless environment

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
                region_name=settings.S3_REGION,
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=settings.S3_CONNECT_TIMEOUT_SECONDS,
                    read_timeout=settings.S3_READ_TIMEOUT_SECONDS,
                    retries={"max_attempts": 2, "mode": "standard"},
                ),
            )

    @property
    def uses_s3(self) -> bool:
        return self._s3_available

    @staticmethod
    def _safe_key(key: str) -> str:
        """Normalise key and block directory-traversal attacks."""
        cleaned = key.strip().replace("\\", "/").strip("/")
        parts = cleaned.split("/")
        if not cleaned or any(p in {".", "..", ""} for p in parts):
            raise ValueError(f"Invalid storage object key: {key!r}")
        return cleaned

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def ensure_ready(self) -> None:
        """Verify or create the configured bucket. Called on app startup."""
        if not self._s3_configured:
            return

        def _check_bucket() -> None:
            assert self._client is not None
            assert settings.S3_BUCKET is not None
            try:
                self._client.head_bucket(Bucket=settings.S3_BUCKET)
            except ClientError as exc:
                code = str(exc.response.get("Error", {}).get("Code", ""))
                if code not in {"404", "NoSuchBucket"}:
                    raise
                self._client.create_bucket(Bucket=settings.S3_BUCKET)

        try:
            await asyncio.to_thread(_check_bucket)
            self._s3_available = True
        except Exception:
            self._s3_available = False
            if settings.S3_REQUIRED:
                raise
            logger.warning("S3-compatible storage unavailable; using local development fallback")

    # ------------------------------------------------------------------
    # Presigned upload URL (bypasses serverless request-body limits)
    # ------------------------------------------------------------------

    def generate_presigned_upload_url(
        self,
        key: str,
        content_type: str,
        expires_in: int = 300,
    ) -> str:
        """Return a presigned S3 PUT URL so the browser can upload directly."""
        if not self._s3_configured or self._client is None or not settings.S3_BUCKET:
            raise RuntimeError("S3 storage is not configured for presigned uploads")
        safe_k = self._safe_key(key)
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET,
                "Key": safe_k,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    # ------------------------------------------------------------------
    # Server-side upload (used for processed / normalised images)
    # ------------------------------------------------------------------

    async def upload_image(self, file_data: bytes, filename: str, content_type: str) -> str:
        key = self._safe_key(filename)
        if self._s3_available:
            assert self._client is not None and settings.S3_BUCKET is not None
            try:
                await asyncio.to_thread(
                    self._client.put_object,
                    Bucket=settings.S3_BUCKET,
                    Key=key,
                    Body=file_data,
                    ContentType=content_type,
                )
            except Exception:
                logger.exception("storage_upload_failed category=s3 key=%s", key)
                raise
            return f"/api/v1/artifacts/{key}"

        # Local development fallback
        path = self.upload_dir / key
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            async with aiofiles.open(path, "wb") as fh:
                await fh.write(file_data)
        except OSError:
            logger.warning("local_storage_write_failed key=%s", key)
            raise
        return f"/uploads/{key}"

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def get_image(self, filename: str) -> tuple[bytes, str]:
        key = self._safe_key(filename)
        if self._s3_available:
            assert self._client is not None and settings.S3_BUCKET is not None

            def _get() -> tuple[bytes, str]:
                resp = self._client.get_object(Bucket=settings.S3_BUCKET, Key=key)
                return resp["Body"].read(), resp.get("ContentType", "application/octet-stream")

            return await asyncio.to_thread(_get)

        path = self.upload_dir / key
        if not path.is_file():
            raise FileNotFoundError(key)
        async with aiofiles.open(path, "rb") as fh:
            return await fh.read(), "application/octet-stream"

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_status(self) -> str:
        if self._s3_configured:
            return "ok" if self._s3_available else "degraded"
        try:
            writable = os.access(self.upload_dir, os.W_OK)
        except OSError:
            writable = False
        if not writable:
            return "error"
        return "degraded" if settings.APP_ENV.lower() == "production" else "ok"


storage_service = StorageService()
