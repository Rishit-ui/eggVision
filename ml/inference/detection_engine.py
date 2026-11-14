"""EggVision AI — Egg Detection Inference Engine.

Integrates trained Ultralytics YOLO egg detector into the EggVision inference pipeline.
Safely falls back to PlaceholderEngine if model weights, metadata, or ML dependencies are unavailable.
Strictly verifies SHA-256 artifact integrity and rejects checkpoints on checksum mismatch.
Preserves scientific honesty: visible egg detection does not fabricate candling freshness metrics.

Production Runtime Requirements:
When deploying actual YOLO model weights (e.g. ml/artifacts/detection/weights/best.pt)
to a backend runtime, the environment requires:
    - ultralytics==8.4.212
    - torch>=2.2.0
    - torchvision>=0.17.0
    - opencv-python-headless>=4.9.0
    - numpy>=1.26.0
These are tracked in ml/requirements.txt. In environments where these packages are
not installed (such as lightweight backend CI test runners), the engine safely
falls back to PlaceholderEngine without crashing.
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

import numpy as np

from .engine import InferenceEngine, ModelInfo, PredictionResult
from .placeholder import PlaceholderEngine

logger = logging.getLogger("detection_engine")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WEIGHTS = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "best.pt"
DEFAULT_METADATA = REPO_ROOT / "ml" / "artifacts" / "detection" / "model_metadata.json"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 digest of a file."""
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class DetectionEngine(InferenceEngine):
    """Real inference engine running trained YOLO egg detector."""

    def __init__(
        self,
        weights_path: Path = DEFAULT_WEIGHTS,
        metadata_path: Path = DEFAULT_METADATA,
        conf_threshold: float = 0.25,
        device: str | None = None,
    ):
        self.weights_path = Path(weights_path)
        self.metadata_path = Path(metadata_path)
        self.conf_threshold = conf_threshold
        self.device = device
        self.model = None
        self._is_ready = False
        self._metadata: dict[str, Any] = {}
        self._load_model()

    def _load_model(self) -> None:
        """Verify artifact integrity and load YOLO weights."""
        if not self.weights_path.exists():
            logger.info(f"Detector weights not found at {self.weights_path}. Remaining uninitialized.")
            self._is_ready = False
            self.model = None
            return

        if self.weights_path.stat().st_size == 0:
            logger.warning(f"Detector weights file at {self.weights_path} is empty.")
            self._is_ready = False
            self.model = None
            return

        # Load metadata if present and enforce SHA-256 checksum integrity
        if self.metadata_path.exists():
            try:
                with self.metadata_path.open("r", encoding="utf-8") as f:
                    self._metadata = json.load(f)
            except Exception as e:
                logger.warning(f"Could not parse model metadata at {self.metadata_path}: {e}")
                self._metadata = {}

            expected_sha = self._metadata.get("weights_sha256")
            if expected_sha:
                actual_sha = compute_sha256(self.weights_path)
                if actual_sha != expected_sha:
                    logger.error(
                        f"Weight SHA-256 mismatch: expected {expected_sha}, got {actual_sha}. "
                        "Rejecting checkpoint to prevent execution of unverified or corrupt weights."
                    )
                    self._is_ready = False
                    self.model = None
                    self._metadata = {}
                    return
        else:
            logger.warning(
                f"Model metadata not found at {self.metadata_path}. Proceeding without declared metadata."
            )
            self._metadata = {}

        try:
            from ultralytics import YOLO

            logger.info(f"Loading YOLO detector from {self.weights_path}...")
            self.model = YOLO(str(self.weights_path))
            self._is_ready = True
            logger.info("Detector successfully loaded and ready for inference.")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            self.model = None
            self._is_ready = False

    def is_ready(self) -> bool:
        """Check if model is loaded and ready."""
        return self._is_ready and self.model is not None

    def get_model_info(self) -> ModelInfo:
        """Return information about the loaded model."""
        if not self.is_ready():
            return ModelInfo(
                version="none",
                model_type="yolo_detection",
                is_ready=False,
                description="Detector weights missing, corrupt, or rejected by integrity check. Fallback active.",
            )

        version = self._metadata.get("model_name", "yolov8n-egg-detector-v1.0")
        dataset_version = self._metadata.get("training_dataset", "afshin-dini/Egg-Detection")
        metrics = self._metadata.get("evaluation_metrics") or self._metadata.get("training_metrics")

        return ModelInfo(
            version=version,
            model_type="yolo_detection",
            is_ready=True,
            description="Trained YOLO egg detection model for visible shell localization.",
            dataset_version=dataset_version,
            metrics=metrics,
        )

    async def predict(self, image: np.ndarray, metadata: dict | None = None) -> PredictionResult:
        """Run egg detection on an input image.

        Args:
            image: BGR numpy image array (H, W, C).
            metadata: Optional dictionary with environmental or batch metadata.

        Returns:
            PredictionResult with detection details, confidence, and latency.
        """
        if not self.is_ready():
            return PredictionResult(
                status="model_not_ready",
                error_message="Detection model is not loaded or verified.",
                model_version="none",
            )

        if image is None or not isinstance(image, np.ndarray) or image.size == 0:
            return PredictionResult(
                status="error",
                error_message="Invalid or empty image array provided.",
                model_version=self.get_model_info().version,
            )

        t0 = time.perf_counter()
        try:
            results = self.model.predict(
                image,
                conf=self.conf_threshold,
                device=self.device,
                verbose=False,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            result = results[0]
            boxes = result.boxes
            n_detected = len(boxes)

            explanations: list[str] = []
            max_conf = 0.0

            if n_detected > 0:
                confs = boxes.conf.cpu().numpy()
                xyxy = boxes.xyxy.cpu().numpy()
                max_conf = float(np.max(confs))
                best_idx = int(np.argmax(confs))
                best_box = xyxy[best_idx].tolist()

                explanations.append(f"Detected {n_detected} egg(s) in frame.")
                explanations.append(
                    f"Primary egg localized at [{best_box[0]:.1f}, {best_box[1]:.1f}, {best_box[2]:.1f}, {best_box[3]:.1f}] "
                    f"with confidence {max_conf:.2%}."
                )
            else:
                explanations.append("No eggs detected in provided image at current confidence threshold.")

            explanations.append(
                "Scientific disclosure: Visible shell detection active; candling internal freshness metrics require candling hardware."
            )

            return PredictionResult(
                status="completed",
                confidence=round(max_conf, 4) if n_detected > 0 else 0.0,
                explanation=explanations,
                inference_time_ms=round(elapsed_ms, 2),
                model_version=self.get_model_info().version,
                # Candling freshness parameters are deliberately left None to preserve scientific integrity
                freshness_class=None,
                freshness_score=None,
                predicted_haugh_unit=None,
                crack_probability=None,
                blood_spot_probability=None,
            )
        except Exception as e:
            logger.error(f"Inference execution failed: {e}")
            return PredictionResult(
                status="error",
                error_message=f"Inference execution failed: {e}",
                model_version=self.get_model_info().version,
            )


def get_inference_engine(
    weights_path: Path | None = None,
    metadata_path: Path | None = None,
) -> InferenceEngine:
    """Factory function returning DetectionEngine if weights exist and pass verification, else PlaceholderEngine."""
    weights = Path(weights_path) if weights_path else DEFAULT_WEIGHTS
    meta = Path(metadata_path) if metadata_path else DEFAULT_METADATA

    if weights.exists() and weights.stat().st_size > 0:
        try:
            engine = DetectionEngine(weights_path=weights, metadata_path=meta)
            if engine.is_ready():
                return engine
            logger.warning(
                "DetectionEngine initialized but is not ready (missing dependencies, corrupt file, or SHA-256 mismatch). "
                "Falling back to PlaceholderEngine."
            )
        except Exception as e:
            logger.warning(f"Could not initialize DetectionEngine: {e}. Falling back to PlaceholderEngine.")

    return PlaceholderEngine()
