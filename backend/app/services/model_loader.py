"""EggVision AI — Model Lifecycle & Artifact Runtime Manager.

Manages startup artifact resolution (local ONNX/PyTorch or private S3 download),
cryptographic SHA-256 verification before execution, caching in ephemeral runtime storage,
and exposes fine-grained readiness telemetry (MODEL_READY, MODEL_NOT_READY,
MODEL_DOWNLOADING, MODEL_INTEGRITY_FAILED, MODEL_ERROR).
"""

import asyncio
import hashlib
import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from app.config import settings

from ml.inference.engine import InferenceEngine
from ml.inference.placeholder import PlaceholderEngine

logger = logging.getLogger("model_loader")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOCAL_ONNX = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "eggvision_detector.onnx"
DEFAULT_LOCAL_PT = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "best.pt"
DEFAULT_LOCAL_MANIFEST = REPO_ROOT / "ml" / "artifacts" / "detection" / "manifest.json"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 digest in chunks."""
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
        """Return the active inference engine (real or placeholder)."""
        return self.engine

    def get_status_summary(self) -> dict[str, Any]:
        """Return full telemetry breakdown of model status."""
        return {
            "state": self.state,
            "artifact_available": self.artifact_available,
            "checksum_verified": self.checksum_verified,
            "runtime_available": self.runtime_available,
            "runtime_name": self.runtime_name,
            "is_ready": self.engine.is_ready(),
            "model_path": str(self.resolved_model_path) if self.resolved_model_path else None,
            "error_message": self.error_message,
        }

    async def initialize(self) -> None:
        """Resolve model artifact, verify SHA-256, and load runtime engine."""
        async with self._lock:
            try:
                await self._do_initialize()
            except Exception as e:
                logger.error(f"Unexpected error during model initialization: {e}", exc_info=True)
                self.state = "MODEL_ERROR"
                self.error_message = str(e)
                self.engine = PlaceholderEngine()

    async def _do_initialize(self) -> None:
        # Step 1: Check explicitly configured MODEL_PATH
        if settings.MODEL_PATH:
            configured_path = Path(settings.MODEL_PATH)
            if configured_path.exists() and configured_path.stat().st_size > 0:
                logger.info(f"Using explicitly configured MODEL_PATH: {configured_path}")
                self.resolved_model_path = configured_path
                self.artifact_available = True

        # Step 2: Check local default ONNX model
        if not self.resolved_model_path and DEFAULT_LOCAL_ONNX.exists() and DEFAULT_LOCAL_ONNX.stat().st_size > 0:
            logger.info(f"Using local default ONNX artifact: {DEFAULT_LOCAL_ONNX}")
            self.resolved_model_path = DEFAULT_LOCAL_ONNX
            self.artifact_available = True

        # Step 3: Check local default PyTorch model
        if not self.resolved_model_path and DEFAULT_LOCAL_PT.exists() and DEFAULT_LOCAL_PT.stat().st_size > 0:
            logger.info(f"Using local default PyTorch checkpoint: {DEFAULT_LOCAL_PT}")
            self.resolved_model_path = DEFAULT_LOCAL_PT
            self.artifact_available = True

        # Step 4: If still not found, attempt download from S3 if configured
        if not self.resolved_model_path:
            s3_model_path = await self._try_download_from_s3()
            if s3_model_path:
                self.resolved_model_path = s3_model_path
                self.artifact_available = True

        # If no artifact could be found
        if not self.resolved_model_path or not self.resolved_model_path.exists():
            logger.info("No model artifact available locally or in S3. Placeholder active.")
            self.state = "MODEL_NOT_READY"
            self.artifact_available = False
            self.checksum_verified = False
            self.engine = PlaceholderEngine()
            return

        # Step 5: Verify SHA-256 Checksum
        self.state = "MODEL_LOADING"
        expected_sha = settings.MODEL_ARTIFACT_SHA256
        if not expected_sha and DEFAULT_LOCAL_MANIFEST.exists():
            try:
                with DEFAULT_LOCAL_MANIFEST.open("r", encoding="utf-8") as f:
                    manifest = json.load(f)
                if self.resolved_model_path.suffix == ".onnx":
                    expected_sha = manifest.get("onnx_artifact", {}).get("sha256")
                else:
                    expected_sha = manifest.get("original_checkpoint", {}).get("sha256")
            except Exception as e:
                logger.warning(f"Could not read manifest for checksum verification: {e}")

        actual_sha = await asyncio.to_thread(compute_sha256, self.resolved_model_path)
        if expected_sha and actual_sha != expected_sha:
            logger.error(
                f"Model integrity failure: expected SHA {expected_sha}, got {actual_sha}. "
                "Rejecting artifact to prevent corrupt or untrusted execution."
            )
            self.state = "MODEL_INTEGRITY_FAILED"
            self.error_message = f"Checksum mismatch: expected {expected_sha}, got {actual_sha}"
            self.checksum_verified = False
            self.engine = PlaceholderEngine()
            return

        self.checksum_verified = True

        # Step 6: Initialize Runtime Engine
        suffix = self.resolved_model_path.suffix.lower()
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
                    self.state = "MODEL_ERROR"
                    self.engine = PlaceholderEngine()
            except Exception as e:
                logger.warning(f"Could not initialize OnnxDetectionEngine: {e}")
                self.state = "MODEL_ERROR"
                self.engine = PlaceholderEngine()

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
                    self.state = "MODEL_ERROR"
                    self.engine = PlaceholderEngine()
            except Exception as e:
                logger.warning(f"Could not initialize DetectionEngine: {e}")
                self.state = "MODEL_ERROR"
                self.engine = PlaceholderEngine()

        else:
            logger.error(f"Unsupported model artifact format: {suffix}")
            self.state = "MODEL_ERROR"
            self.engine = PlaceholderEngine()

    async def _try_download_from_s3(self) -> Path | None:
        """Download model artifact from private S3 into temporary runtime directory."""
        s3_endpoint = settings.MODEL_S3_ENDPOINT or settings.S3_ENDPOINT
        s3_bucket = settings.MODEL_S3_BUCKET or settings.S3_BUCKET
        s3_key = settings.MODEL_ARTIFACT_KEY
        access_key = settings.MODEL_S3_ACCESS_KEY or settings.S3_ACCESS_KEY
        secret_key = settings.MODEL_S3_SECRET_KEY or settings.S3_SECRET_KEY
        region = settings.MODEL_S3_REGION or settings.S3_REGION

        if not (s3_endpoint and s3_bucket and s3_key and access_key and secret_key):
            logger.info("S3 model download not configured (missing endpoint, bucket, or key).")
            return None

        self.state = "MODEL_DOWNLOADING"
        cache_dir = Path(tempfile.gettempdir()) / "eggvision_models"
        cache_dir.mkdir(parents=True, exist_ok=True)
        filename = Path(s3_key).name or "model.onnx"
        cached_file = cache_dir / filename

        # Check if already cached and valid
        if cached_file.exists() and cached_file.stat().st_size > 0 and settings.MODEL_ARTIFACT_SHA256:
            existing_sha = await asyncio.to_thread(compute_sha256, cached_file)
            if existing_sha == settings.MODEL_ARTIFACT_SHA256:
                logger.info(f"Using verified cached model from {cached_file}")
                return cached_file
            else:
                logger.warning("Cached model checksum mismatch. Re-downloading from S3.")
                cached_file.unlink()

        def _download() -> None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                endpoint_url=s3_endpoint,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
                config=Config(signature_version="s3v4", connect_timeout=15.0, read_timeout=60.0),
            )
            logger.info(f"Downloading model artifact s3://{s3_bucket}/{s3_key} to {cached_file}...")
            client.download_file(s3_bucket, s3_key, str(cached_file))

        try:
            await asyncio.to_thread(_download)
            if cached_file.exists() and cached_file.stat().st_size > 0:
                logger.info(f"Downloaded model artifact successfully: {cached_file.stat().st_size:,} bytes")
                return cached_file
        except Exception as e:
            logger.warning(f"Failed to download model artifact from S3: {e}")
            if cached_file.exists():
                cached_file.unlink()

        return None


model_manager = ModelLifecycleManager()
