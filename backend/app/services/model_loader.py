"""EggVision AI — Model Lifecycle & Artifact Runtime Manager.

Manages startup artifact resolution (local ONNX or private Cloudflare R2 / S3 download),
cryptographic SHA-256 verification before execution, atomic caching in content-addressed
runtime storage (/tmp/eggvision_models/<sha256>/model.onnx), and exposes fine-grained
readiness telemetry (MODEL_READY, MODEL_NOT_READY, MODEL_DOWNLOADING, MODEL_INTEGRITY_FAILED,
MODEL_ERROR).
"""

import asyncio
import hashlib
import hmac
import json
import logging
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any

from app.config import settings

from ml.inference.engine import InferenceEngine
from ml.inference.manifest_validator import (
    validate_manifest_dict,
    validate_sha256_format,
)
from ml.inference.placeholder import PlaceholderEngine

logger = logging.getLogger("model_loader")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOCAL_ONNX = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "eggvision_detector.onnx"
DEFAULT_LOCAL_PT = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "best.pt"
DEFAULT_LOCAL_MANIFEST = REPO_ROOT / "ml" / "artifacts" / "detection" / "manifest.json"

HEX_SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 digest in 64KB chunks."""
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class ModelLifecycleManager:
    """Manages model artifact retrieval, integrity verification, and runtime engine lifecycle."""

    def __init__(self) -> None:
        self.state: str = "MODEL_NOT_READY"
        self.artifact_available: bool = False
        self.checksum_verified: bool = False
        self.runtime_available: bool = False
        self.runtime_name: str | None = None
        self.resolved_model_path: Path | None = None
        self.error_message: str | None = None
        self.engine: InferenceEngine = PlaceholderEngine()
        self._lock = asyncio.Lock()

    def get_engine(self) -> InferenceEngine:
        """Return a real engine only when the complete verified lifecycle is ready."""
        if self._is_fully_ready():
            return self.engine
        if not isinstance(self.engine, PlaceholderEngine):
            self.engine = PlaceholderEngine()
        return self.engine

    def _is_fully_ready(self) -> bool:
        return bool(
            self.state == "MODEL_READY"
            and self.artifact_available
            and self.checksum_verified
            and self.runtime_available
            and self.engine.is_ready()
        )

    def _reset_state(self) -> None:
        self.state = "MODEL_NOT_READY"
        self.artifact_available = False
        self.checksum_verified = False
        self.runtime_available = False
        self.runtime_name = None
        self.resolved_model_path = None
        self.error_message = None
        self.engine = PlaceholderEngine()

    def _reject_integrity(self, message: str) -> None:
        self.state = "MODEL_INTEGRITY_FAILED"
        self.checksum_verified = False
        self.runtime_available = False
        self.runtime_name = None
        self.error_message = message
        self.engine = PlaceholderEngine()

    def _runtime_failed(self, message: str) -> None:
        self.state = "MODEL_ERROR"
        self.runtime_available = False
        self.runtime_name = None
        self.error_message = message
        self.engine = PlaceholderEngine()

    def get_status_summary(self) -> dict[str, Any]:
        """Return full telemetry breakdown of model status without leaking host paths."""
        sanitized_model_ref = self.resolved_model_path.name if self.resolved_model_path else None
        return {
            "state": self.state,
            "artifact_available": self.artifact_available,
            "checksum_verified": self.checksum_verified,
            "runtime_available": self.runtime_available,
            "runtime_name": self.runtime_name,
            "is_ready": self._is_fully_ready(),
            "model_reference": sanitized_model_ref,
            "error_message": self.error_message,
        }

    async def initialize(self) -> None:
        """Resolve model artifact, verify SHA-256, and load runtime engine."""
        async with self._lock:
            self._reset_state()
            try:
                await self._do_initialize()
            except Exception as e:
                logger.error(f"Unexpected error during model initialization: {e}", exc_info=True)
                self._runtime_failed("Unexpected model initialization failure.")

    async def _do_initialize(self) -> None:
        # Step 1: Check explicitly configured MODEL_PATH
        if settings.MODEL_PATH:
            configured_path = Path(settings.MODEL_PATH)
            if configured_path.exists() and configured_path.stat().st_size > 0:
                logger.info(f"Using explicitly configured MODEL_PATH: {configured_path.name}")
                self.resolved_model_path = configured_path
                self.artifact_available = True

        # Step 2: Check local default ONNX model
        if not self.resolved_model_path and DEFAULT_LOCAL_ONNX.exists() and DEFAULT_LOCAL_ONNX.stat().st_size > 0:
            logger.info("Using local default ONNX artifact")
            self.resolved_model_path = DEFAULT_LOCAL_ONNX
            self.artifact_available = True

        # Step 3: Check local default PyTorch model (allowed in dev only)
        if not self.resolved_model_path and DEFAULT_LOCAL_PT.exists() and DEFAULT_LOCAL_PT.stat().st_size > 0:
            logger.info("Using local default PyTorch checkpoint")
            self.resolved_model_path = DEFAULT_LOCAL_PT
            self.artifact_available = True

        # Step 4: If still not found, attempt download from S3/R2 if configured
        if not self.resolved_model_path:
            s3_model_path = await self._try_download_from_s3()
            if s3_model_path:
                self.resolved_model_path = s3_model_path
                self.artifact_available = True

        # If no artifact could be found
        if not self.resolved_model_path or not self.resolved_model_path.exists():
            logger.info("No model artifact available locally or in S3/R2. Placeholder active.")
            self.state = "MODEL_NOT_READY"
            self.artifact_available = False
            self.checksum_verified = False
            self.engine = PlaceholderEngine()
            return

        suffix = self.resolved_model_path.suffix.lower()

        # Step 5: Production safety check: Prohibit PyTorch (.pt) in production
        is_production = settings.APP_ENV.lower() == "production"
        if is_production and suffix != ".onnx":
            logger.error("Production strictly requires verified ONNX (.onnx) runtime. PyTorch checkpoints (.pt) are prohibited.")
            self._reject_integrity("Production requires verified ONNX runtime; PyTorch checkpoints are prohibited.")
            return

        # Step 6: Verify SHA-256 Checksum
        self.state = "MODEL_LOADING"
        expected_sha = settings.MODEL_ARTIFACT_SHA256

        # Check local manifest if expected_sha is not explicitly in settings
        if not expected_sha and DEFAULT_LOCAL_MANIFEST.exists():
            try:
                with DEFAULT_LOCAL_MANIFEST.open("r", encoding="utf-8") as f:
                    manifest = json.load(f)
                manifest = validate_manifest_dict(manifest)
                if suffix == ".onnx":
                    expected_sha = manifest.get("onnx_artifact", {}).get("sha256")
                else:
                    expected_sha = manifest.get("original_checkpoint", {}).get("sha256")
            except Exception as e:
                logger.warning(f"Could not read/validate local manifest: {e}")

        # Missing expected hash is rejected immediately
        if not expected_sha:
            logger.error("Model integrity failure: no expected SHA-256 checksum is configured or found in manifest.")
            self._reject_integrity("Expected SHA-256 checksum is missing.")
            return

        try:
            expected_sha = validate_sha256_format(expected_sha)
        except Exception as e:
            logger.error(f"Configured SHA-256 checksum is malformed: {e}")
            self._reject_integrity("Expected SHA-256 checksum is invalid.")
            return

        actual_size = self.resolved_model_path.stat().st_size
        if actual_size == 0:
            logger.error(f"Model artifact {self.resolved_model_path.name} is empty (0 bytes).")
            self._reject_integrity("Model artifact is empty (0 bytes).")
            return

        actual_sha = await asyncio.to_thread(compute_sha256, self.resolved_model_path)
        if not hmac.compare_digest(actual_sha, expected_sha):
            logger.error(
                f"Model integrity failure: expected SHA-256 {expected_sha}, got {actual_sha}. "
                "Rejecting artifact to prevent corrupt or untrusted execution."
            )
            self._reject_integrity("Model artifact checksum mismatch.")
            return

        self.checksum_verified = True

        # Step 7: Initialize Runtime Engine
        if suffix == ".onnx":
            try:
                from ml.inference.onnx_detection_engine import OnnxDetectionEngine

                engine = OnnxDetectionEngine(model_path=self.resolved_model_path)
                if engine.is_ready():
                    self.engine = engine
                    self.state = "MODEL_READY"
                    self.runtime_available = True
                    self.runtime_name = "onnxruntime"
                    logger.info("ModelLifecycleManager: ONNX detection engine initialized successfully.")
                    return
                else:
                    logger.warning("OnnxDetectionEngine failed is_ready check.")
                    self._runtime_failed("ONNX Runtime engine failed its readiness check.")
            except Exception as e:
                logger.warning(f"Could not initialize OnnxDetectionEngine: {e}")
                self._runtime_failed("ONNX Runtime initialization failed.")

        elif suffix == ".pt":
            try:
                from ml.inference.detection_engine import DetectionEngine

                engine = DetectionEngine(weights_path=self.resolved_model_path)
                if engine.is_ready():
                    self.engine = engine
                    self.state = "MODEL_READY"
                    self.runtime_available = True
                    self.runtime_name = "ultralytics"
                    logger.info("ModelLifecycleManager: PyTorch detection engine initialized successfully.")
                    return
                else:
                    logger.warning("DetectionEngine failed is_ready check.")
                    self._runtime_failed("PyTorch runtime engine failed its readiness check.")
            except Exception as e:
                logger.warning(f"Could not initialize DetectionEngine: {e}")
                self._runtime_failed("PyTorch runtime initialization failed.")

        else:
            logger.error(f"Unsupported model artifact format: {suffix}")
            self._runtime_failed("Unsupported model artifact format.")

    async def _try_download_from_s3(self) -> Path | None:
        """Download model artifact from private S3 / Cloudflare R2 into content-addressed cache.

        Strict boundary: Uses only MODEL_S3_* configuration; never reuses image-upload S3_* settings.
        """
        s3_endpoint = settings.MODEL_S3_ENDPOINT
        s3_bucket = settings.MODEL_S3_BUCKET or "eggvision-models"
        s3_key = settings.MODEL_ARTIFACT_KEY
        access_key = settings.MODEL_S3_ACCESS_KEY
        secret_key = settings.MODEL_S3_SECRET_KEY
        region = settings.MODEL_S3_REGION or "auto"

        if not (s3_endpoint and s3_bucket and s3_key and access_key and secret_key):
            logger.info("MODEL_S3_* download not configured (missing endpoint, bucket, key, or credentials).")
            return None

        expected_sha = settings.MODEL_ARTIFACT_SHA256
        if not expected_sha:
            logger.error("Cannot download model from S3/R2 without a declared MODEL_ARTIFACT_SHA256.")
            self._reject_integrity("Expected SHA-256 checksum is missing.")
            return None

        try:
            expected_sha = validate_sha256_format(expected_sha)
        except Exception:
            logger.error(f"Declared MODEL_ARTIFACT_SHA256 '{expected_sha}' is not valid 64-hex SHA-256.")
            self._reject_integrity("Expected SHA-256 checksum is invalid.")
            return None

        self.state = "MODEL_DOWNLOADING"

        # Content-addressed cache directory: /tmp/eggvision_models/<sha256>/model.onnx
        cache_base = Path(tempfile.gettempdir()) / "eggvision_models"
        cache_dir = cache_base / expected_sha
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached_file = cache_dir / "model.onnx"

        # Check if verified model is already cached
        if cached_file.exists() and cached_file.stat().st_size > 0:
            existing_sha = await asyncio.to_thread(compute_sha256, cached_file)
            if hmac.compare_digest(existing_sha, expected_sha):
                logger.info(f"Using verified content-addressed cached model from {cached_file.name}")
                return cached_file
            else:
                logger.warning("Cached model checksum mismatch. Evicting corrupted cache entry.")
                cached_file.unlink()

        # Temporary partial download file to prevent partial writes from corrupting cache
        tmp_download_file = cache_dir / f".download_{uuid.uuid4().hex[:12]}.part"

        def _download() -> None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                endpoint_url=s3_endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
                config=Config(
                    signature_version="s3v4",
                    connect_timeout=10.0,
                    read_timeout=30.0,
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            )
            logger.info(f"Downloading model artifact s3://{s3_bucket}/{s3_key} to temp file...")
            client.download_file(s3_bucket, s3_key, str(tmp_download_file))

        try:
            await asyncio.to_thread(_download)

            if not tmp_download_file.exists() or tmp_download_file.stat().st_size == 0:
                raise ValueError("Downloaded file is empty or missing.")

            # Verify integrity on the downloaded temp file before moving to cache
            downloaded_sha = await asyncio.to_thread(compute_sha256, tmp_download_file)
            if not hmac.compare_digest(downloaded_sha, expected_sha):
                raise ValueError(
                    f"Downloaded artifact checksum mismatch: expected {expected_sha}, got {downloaded_sha}"
                )

            # Atomic rename into permanent cache path
            tmp_download_file.replace(cached_file)
            logger.info(f"Downloaded model artifact successfully and verified: {cached_file.stat().st_size:,} bytes")
            return cached_file

        except Exception as e:
            logger.error(f"Failed to download model artifact from S3/R2: {e}")
            self.error_message = f"S3/R2 download failed: {e}"
            return None

        finally:
            # Ensure partial temporary file is always cleaned up on failure
            if tmp_download_file.exists():
                try:
                    tmp_download_file.unlink()
                except OSError:
                    pass


model_manager = ModelLifecycleManager()
