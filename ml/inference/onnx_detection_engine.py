"""EggVision AI — Production ONNX Runtime Detection Inference Engine.

Lightweight, high-performance CPU inference engine running the trained YOLOv8n
egg detector using ONNX Runtime. Enforces SHA-256 artifact integrity before session
creation, handles missing dependencies gracefully, and implements letterbox
preprocessing, coordinate decoding, and Non-Maximum Suppression.
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .engine import InferenceEngine, ModelInfo, PredictionResult
from .placeholder import PlaceholderEngine

logger = logging.getLogger("onnx_detection_engine")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ONNX_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "eggvision_detector.onnx"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "manifest.json"
DEFAULT_METADATA_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "onnx_metadata.json"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 digest of a file in 64KB chunks."""
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def letterbox_image(
    image: np.ndarray,
    target_size: int = 640,
) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize image to square target size with aspect-ratio preserving padding."""
    h, w = image.shape[:2]
    scale = min(target_size / h, target_size / w)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    pad_x = (target_size - nw) / 2
    pad_y = (target_size - nh) / 2
    top = int(round(pad_y - 0.1))
    bottom = int(round(pad_y + 0.1))
    left = int(round(pad_x - 0.1))
    right = int(round(pad_x + 0.1))

    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)
    letterboxed = cv2.copyMakeBorder(
        resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
    )
    return letterboxed, scale, (left, top)


class OnnxDetectionEngine(InferenceEngine):
    """Production ONNX Runtime inference engine for EggVision egg detection."""

    def __init__(
        self,
        model_path: Path = DEFAULT_ONNX_PATH,
        metadata_path: Path | None = None,
        conf_threshold: float = 0.25,
        iou_threshold: float = 0.70,
        target_size: int = 640,
    ) -> None:
        self.model_path = Path(model_path)
        self.metadata_path = Path(metadata_path) if metadata_path else DEFAULT_MANIFEST_PATH
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.target_size = target_size

        self.session = None
        self._is_ready = False
        self._metadata: dict[str, Any] = {}
        self._input_name: str | None = None
        self._load_model()

    def _load_model(self) -> None:
        """Verify SHA-256 integrity and initialize ONNX Runtime session."""
        if not self.model_path.exists():
            logger.info(f"ONNX model not found at {self.model_path}. Engine uninitialized.")
            self._is_ready = False
            self.session = None
            return

        if self.model_path.stat().st_size == 0:
            logger.warning(f"ONNX model file at {self.model_path} is empty (0 bytes).")
            self._is_ready = False
            self.session = None
            return

        # Load metadata/manifest if available
        meta_to_try = [self.metadata_path, DEFAULT_METADATA_PATH]
        for mp in meta_to_try:
            if mp and mp.exists():
                try:
                    with mp.open("r", encoding="utf-8") as f:
                        self._metadata = json.load(f)
                    break
                except Exception as e:
                    logger.warning(f"Could not load metadata from {mp}: {e}")

        # Check declared SHA-256 checksum
        expected_sha = (
            self._metadata.get("onnx_artifact", {}).get("sha256")
            or self._metadata.get("onnx_sha256")
        )
        if expected_sha:
            actual_sha = compute_sha256(self.model_path)
            if actual_sha != expected_sha:
                logger.error(
                    f"ONNX SHA-256 mismatch for {self.model_path.name}: "
                    f"expected {expected_sha}, got {actual_sha}. Rejecting checkpoint."
                )
                self._is_ready = False
                self.session = None
                self._metadata = {}
                return

        # Initialize ONNX Runtime session
        try:
            import onnxruntime as ort

            logger.info(f"Loading ONNX detection model from {self.model_path}...")
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 2
            opts.inter_op_num_threads = 1
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self.session = ort.InferenceSession(
                str(self.model_path),
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            inputs = self.session.get_inputs()
            if not inputs:
                raise ValueError("ONNX model has no input tensors.")
            self._input_name = inputs[0].name
            self._is_ready = True
            logger.info("ONNX detection engine successfully loaded and ready for inference.")

        except Exception as e:
            logger.error(f"Failed to initialize ONNX Runtime session: {e}")
            self.session = None
            self._is_ready = False

    def is_ready(self) -> bool:
        """Check if ONNX runtime session is active."""
        return self._is_ready and self.session is not None

    def get_model_info(self) -> ModelInfo:
        """Return information about the loaded ONNX model."""
        if not self.is_ready():
            return ModelInfo(
                version="none",
                model_type="yolov8n_onnx_detection",
                is_ready=False,
                description="ONNX detector weights missing, corrupt, or rejected by integrity check. Fallback active.",
            )

        version = self._metadata.get("model_version") or self._metadata.get("model_name", "eggvision_detector_yolov8n_v1.0")
        dataset_version = self._metadata.get("provenance", {}).get("dataset_source", "afshin-dini/Egg-Detection")
        metrics = self._metadata.get("evaluation_metrics") or self._metadata.get("onnx_equivalence")

        return ModelInfo(
            version=str(version),
            model_type="yolov8n_onnx_detection",
            is_ready=True,
            description="Production ONNX Runtime YOLOv8n detector for visible shell localization.",
            dataset_version=dataset_version,
            metrics=metrics,
        )

    async def predict(self, image: np.ndarray, metadata: dict | None = None) -> PredictionResult:
        """Run egg detection on input BGR image using ONNX Runtime.

        Args:
            image: BGR numpy image array (H, W, C).
            metadata: Optional dictionary with environmental or batch metadata.

        Returns:
            PredictionResult with localized bounding boxes, confidence, and latency.
        """
        if not self.is_ready():
            return PredictionResult(
                status="model_not_ready",
                error_message="ONNX detection model is not loaded or verified.",
                model_version="none",
            )

        if image is None or not isinstance(image, np.ndarray) or image.size == 0 or len(image.shape) < 2:
            return PredictionResult(
                status="error",
                error_message="Invalid or empty image array provided.",
                model_version=self.get_model_info().version,
            )

        h, w = image.shape[:2]
        t0 = time.perf_counter()

        try:
            letterboxed, scale, (left, top) = letterbox_image(image, self.target_size)

            # Preprocessing: BGR -> RGB, float32, normalize [0, 1], BCHW shape
            if len(letterboxed.shape) == 2:
                letterboxed = cv2.cvtColor(letterboxed, cv2.COLOR_GRAY2BGR)
            elif letterboxed.shape[2] == 4:
                letterboxed = cv2.cvtColor(letterboxed, cv2.COLOR_BGRA2BGR)

            blob = letterboxed[:, :, ::-1].astype(np.float32) / 255.0
            blob = np.transpose(blob, (2, 0, 1))[None, ...]

            outputs = self.session.run(None, {self._input_name: blob})
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            raw_preds = np.squeeze(outputs[0]).T  # Shape: [8400, 5]
            scores = raw_preds[:, 4]
            mask = scores >= self.conf_threshold
            filtered_boxes = raw_preds[mask]
            filtered_scores = scores[mask]

            detected_boxes: list[list[float]] = []
            detected_scores: list[float] = []

            if len(filtered_boxes) > 0:
                cx = filtered_boxes[:, 0]
                cy = filtered_boxes[:, 1]
                bw = filtered_boxes[:, 2]
                bh = filtered_boxes[:, 3]

                x1 = np.clip((cx - bw / 2 - left) / scale, 0, w)
                y1 = np.clip((cy - bh / 2 - top) / scale, 0, h)
                x2 = np.clip((cx + bw / 2 - left) / scale, 0, w)
                y2 = np.clip((cy + bh / 2 - top) / scale, 0, h)

                cv_boxes = [
                    [float(x1[i]), float(y1[i]), float(x2[i] - x1[i]), float(y2[i] - y1[i])]
                    for i in range(len(x1))
                ]
                indices = cv2.dnn.NMSBoxes(
                    cv_boxes,
                    filtered_scores.tolist(),
                    score_threshold=self.conf_threshold,
                    nms_threshold=self.iou_threshold,
                )

                flat_indices = np.array(indices).flatten() if len(indices) > 0 else []
                for idx in flat_indices:
                    i = int(idx)
                    detected_boxes.append([
                        round(float(x1[i]), 1),
                        round(float(y1[i]), 1),
                        round(float(x2[i]), 1),
                        round(float(y2[i]), 1),
                    ])
                    detected_scores.append(round(float(filtered_scores[i]), 4))

            n_detected = len(detected_boxes)
            explanations: list[str] = []
            max_conf = 0.0

            if n_detected > 0:
                max_conf = max(detected_scores)
                best_idx = int(np.argmax(detected_scores))
                best_box = detected_boxes[best_idx]
                explanations.append(f"Detected {n_detected} egg(s) in frame.")
                explanations.append(
                    f"Primary egg localized at [{best_box[0]:.1f}, {best_box[1]:.1f}, {best_box[2]:.1f}, {best_box[3]:.1f}] "
                    f"with confidence {max_conf:.2%}."
                )
            else:
                explanations.append(
                    "No eggs detected in provided image at current confidence threshold."
                )

            explanations.append(
                "Scientific disclosure: Visible shell detection active; candling internal freshness metrics require candling hardware."
            )

            return PredictionResult(
                status="completed",
                confidence=round(max_conf, 4) if n_detected > 0 else 0.0,
                explanation=explanations,
                inference_time_ms=round(elapsed_ms, 2),
                model_version=self.get_model_info().version,
                # Candling freshness parameters intentionally left None
                freshness_class=None,
                freshness_score=None,
                predicted_haugh_unit=None,
                crack_probability=None,
                blood_spot_probability=None,
            )

        except Exception as e:
            logger.error(f"ONNX inference execution failed: {e}")
            return PredictionResult(
                status="error",
                error_message=f"ONNX inference execution failed: {e}",
                model_version=self.get_model_info().version,
            )


def get_onnx_inference_engine(
    model_path: Path | None = None,
    metadata_path: Path | None = None,
) -> InferenceEngine:
    """Factory returning OnnxDetectionEngine if model exists and passes integrity check, else PlaceholderEngine."""
    path = Path(model_path) if model_path else DEFAULT_ONNX_PATH
    meta = Path(metadata_path) if metadata_path else DEFAULT_MANIFEST_PATH

    if path.exists() and path.stat().st_size > 0:
        try:
            engine = OnnxDetectionEngine(model_path=path, metadata_path=meta)
            if engine.is_ready():
                return engine
            logger.warning(
                "OnnxDetectionEngine failed initialization or integrity verification. "
                "Falling back to PlaceholderEngine."
            )
        except Exception as e:
            logger.warning(
                f"Could not initialize OnnxDetectionEngine: {e}. Falling back to PlaceholderEngine."
            )

    return PlaceholderEngine()
