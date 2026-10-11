"""EggVision AI - Computer Vision & Optical Preprocessing Package."""

from .quality import ImageQualityAssessor, QualityReport, QualityWarning
from .detector import EggDetector, DetectionResult
from .segmentation import EggSegmenter, SegmentationResult, EggGeometry
from .normalizer import EggNormalizer, NormalizationResult
from .pipeline import VisionPipeline, PipelineResult

__all__ = [
    "ImageQualityAssessor",
    "QualityReport",
    "QualityWarning",
    "EggDetector",
    "DetectionResult",
    "EggSegmenter",
    "SegmentationResult",
    "EggGeometry",
    "EggNormalizer",
    "NormalizationResult",
    "VisionPipeline",
    "PipelineResult",
]
