"""EggVision AI - Computer Vision & Optical Preprocessing Package."""

from .detector import DetectionResult, EggDetector
from .normalizer import EggNormalizer, NormalizationResult
from .pipeline import PipelineResult, VisionPipeline
from .quality import ImageQualityAssessor, QualityReport, QualityWarning
from .segmentation import EggGeometry, EggSegmenter, SegmentationResult

__all__ = [
    "DetectionResult",
    "EggDetector",
    "EggGeometry",
    "EggNormalizer",
    "EggSegmenter",
    "ImageQualityAssessor",
    "NormalizationResult",
    "PipelineResult",
    "QualityReport",
    "QualityWarning",
    "SegmentationResult",
    "VisionPipeline",
]
