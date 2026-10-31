"""Unified Computer Vision Pipeline for Egg Candling Images.

Orchestrates:
1. Egg Detection
2. Image Quality Assessment & Gating
3. Segmentation & Morphometric Feature Extraction
4. Image Normalization & Optical Enhancement
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import numpy as np
import cv2

from .quality import ImageQualityAssessor, QualityReport, QualityWarning
from .detector import EggDetector, DetectionResult
from .segmentation import EggSegmenter, SegmentationResult, EggGeometry
from .normalizer import EggNormalizer, NormalizationResult


@dataclass
class PipelineResult:
    """End-to-end outcome of computer vision processing on an egg image."""
    quality: QualityReport
    detection: DetectionResult
    segmentation: Optional[SegmentationResult] = None
    normalization: Optional[NormalizationResult] = None
    can_proceed_to_inference: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert pipeline results to JSON-serializable dictionary."""
        out = {
            "image_quality": self.quality.image_quality,
            # This field remains for backwards-compatible persistence only.
            # It is always null: no calibrated capture-readiness score exists.
            "quality_score": self.quality.quality_score,
            "warnings": self.quality.warnings,
            "retake_recommended": self.quality.retake_recommended,
            "recommendation": self.quality.recommendation,
            "can_proceed_to_inference": self.can_proceed_to_inference,
            "metrics": self.quality.metrics,
            "analysis": {
                "status": self.detection.status,
                "capture_mode": self.detection.capture_mode,
                "model": {
                    "name": self.detection.algorithm,
                    "version": "2",
                    "task": "non_ml_candidate_contour_screen",
                    "validated_egg_detector": False,
                },
                "detections": [],
                "limitations": [
                    "No trained, validated egg detector is installed.",
                    (
                        "A contour compatible with the candling chamber silhouette is not proof that an egg is present."
                        if self.detection.capture_mode == "controlled_candling"
                        else "A candidate contour is an optical shape observation and does not prove that an egg is present."
                    ),
                    "Capture-quality measurements are engineering screening metrics, not AI confidence or egg-quality predictions.",
                    "No defect, freshness, spoilage, contamination, or food-safety assessment was performed.",
                ],
                "message": self.detection.message,
            },
        }
        if self.segmentation and self.segmentation.success:
            geo = self.segmentation.geometry
            out["candidate_geometry"] = {
                "area": geo.area,
                "width": geo.width,
                "height": geo.height,
                "aspect_ratio": geo.aspect_ratio,
                "centroid": [geo.centroid_x, geo.centroid_y],
                "orientation_deg": geo.orientation_deg,
                "solidity": geo.solidity,
                "perimeter": geo.perimeter,
                "eccentricity": geo.eccentricity,
                "segmentation_status": geo.segmentation_status,
            }
        return out


class VisionPipeline:
    """Master CV pipeline for egg candling analysis."""

    def __init__(
        self,
        assessor: Optional[ImageQualityAssessor] = None,
        detector: Optional[EggDetector] = None,
        segmenter: Optional[EggSegmenter] = None,
        normalizer: Optional[EggNormalizer] = None
    ):
        self.assessor = assessor or ImageQualityAssessor()
        self.detector = detector or EggDetector()
        self.segmenter = segmenter or EggSegmenter()
        self.normalizer = normalizer or EggNormalizer()

    def process(self, image_bgr: np.ndarray) -> PipelineResult:
        """Run the end-to-end vision pipeline."""
        if image_bgr is None or image_bgr.size == 0:
            quality = self.assessor.assess(image_bgr, screening_status="INVALID_IMAGE")
            detection = DetectionResult(found=False, status="INVALID_IMAGE", message="Empty image.")
            return PipelineResult(quality=quality, detection=detection, can_proceed_to_inference=False)

        # 1. Egg Detection
        detection = self.detector.detect(image_bgr)

        # 2. Quality Assessment with detection context
        quality = self.assessor.assess(
            image_bgr=image_bgr,
            bbox=detection.bbox,
            candidate_mask=detection.candidate_mask,
            screening_status=detection.status,
        )

        # Add multiple eggs warning if detected
        if detection.status == "MULTIPLE_CANDIDATES":
            quality.warnings.append(QualityWarning.MULTIPLE_CANDIDATES)
            quality.retake_recommended = True
            quality.image_quality = "POOR"
            quality.recommendation = "Multiple isolated candidates were screened. Capture one subject at a time; this screen cannot establish egg identity."
            return PipelineResult(
                quality=quality,
                detection=detection,
                can_proceed_to_inference=False,
                error=quality.recommendation,
            )

        # If the capture is unsuitable or no candidate was screened: do not normalize or infer.
        if quality.image_quality in {"POOR", "INCONCLUSIVE"} or not detection.found:
            return PipelineResult(
                quality=quality,
                detection=detection,
                can_proceed_to_inference=False,
                error=quality.recommendation or "Image quality below threshold."
            )

        # 3. Segmentation
        segmentation = self.segmenter.segment(image_bgr, contour_hint=detection.contour)
        if not segmentation.success:
            return PipelineResult(
                quality=quality,
                detection=detection,
                segmentation=segmentation,
                can_proceed_to_inference=False,
                error="Failed to segment egg boundary."
            )

        # 4. Normalization
        normalization = self.normalizer.normalize(
            image_bgr=image_bgr,
            mask=segmentation.mask,
            geometry=segmentation.geometry
        )

        # The contour is retained only as a research candidate.  Its geometry is
        # deliberately not used as evidence of egg identity and never permits
        # egg-specific inference without a validated detection model.
        return PipelineResult(
            quality=quality,
            detection=detection,
            segmentation=segmentation,
            normalization=normalization,
            can_proceed_to_inference=False,
            error="A candidate contour was found, but egg identity is unverified because no validated egg detector is installed.",
        )
