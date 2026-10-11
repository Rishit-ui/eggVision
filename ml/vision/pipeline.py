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
            "quality_score": self.quality.quality_score,
            "warnings": self.quality.warnings,
            "retake_recommended": self.quality.retake_recommended,
            "recommendation": self.quality.recommendation,
            "can_proceed_to_inference": self.can_proceed_to_inference,
            "metrics": self.quality.metrics,
        }
        if self.segmentation and self.segmentation.success:
            geo = self.segmentation.geometry
            out["geometry"] = {
                "area": geo.area,
                "width": geo.width,
                "height": geo.height,
                "aspect_ratio": geo.aspect_ratio,
                "centroid": [geo.centroid_x, geo.centroid_y],
                "orientation_deg": geo.orientation_deg
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
            quality = self.assessor.assess(image_bgr, has_egg=False)
            detection = DetectionResult(found=False, message="Empty image.")
            return PipelineResult(quality=quality, detection=detection, can_proceed_to_inference=False)

        # 1. Egg Detection
        detection = self.detector.detect(image_bgr)

        # 2. Quality Assessment with detection context
        quality = self.assessor.assess(
            image_bgr=image_bgr,
            bbox=detection.bbox,
            has_egg=detection.found
        )

        # Add multiple eggs warning if detected
        if detection.egg_count > 1:
            quality.warnings.append(QualityWarning.MULTIPLE_EGGS)
            quality.retake_recommended = True
            quality.recommendation = "Place only one egg in the candling chamber at a time."

        # If image quality is POOR or egg not found: DO NOT FORCE PREDICTION
        if quality.image_quality == "POOR" or not detection.found:
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

        return PipelineResult(
            quality=quality,
            detection=detection,
            segmentation=segmentation,
            normalization=normalization,
            can_proceed_to_inference=True
        )
