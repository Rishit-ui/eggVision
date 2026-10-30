"""Unit tests for ROI-only capture-quality measurements."""

import cv2
import numpy as np

from ml.vision.detector import EggDetector
from ml.vision.quality import ImageQualityAssessor, QualityWarning


def candidate_image(brightness: int = 180, background: int = 245) -> tuple[np.ndarray, np.ndarray, tuple[int, int, int, int]]:
    image = np.full((400, 300, 3), background, dtype=np.uint8)
    mask = np.zeros((400, 300), dtype=np.uint8)
    cv2.ellipse(image, (150, 200), (60, 100), 0, 0, 360, (brightness - 35, brightness - 10, brightness), -1)
    cv2.ellipse(mask, (150, 200), (60, 100), 0, 0, 360, 255, -1)
    return image, mask, (90, 100, 120, 200)


def test_white_background_does_not_imply_roi_overexposure() -> None:
    image, mask, bbox = candidate_image()
    report = ImageQualityAssessor().assess(image, bbox=bbox, candidate_mask=mask)
    assert QualityWarning.OVEREXPOSED not in report.warnings
    assert report.metrics["exposure_region"] == "candidate_roi"
    assert report.quality_score is None


def test_candidate_exposure_is_reported_only_with_a_candidate_roi() -> None:
    image, mask, bbox = candidate_image(255, 10)
    report = ImageQualityAssessor().assess(image, bbox=bbox, candidate_mask=mask)
    assert QualityWarning.OVEREXPOSED in report.warnings

    no_roi = ImageQualityAssessor().assess(np.full((300, 300, 3), 253, dtype=np.uint8))
    assert QualityWarning.EXPOSURE_INCONCLUSIVE in no_roi.warnings
    assert QualityWarning.OVEREXPOSED not in no_roi.warnings


def test_blur_and_border_clipping_use_candidate_geometry() -> None:
    image, mask, bbox = candidate_image(180, 10)
    blurred = cv2.GaussianBlur(image, (41, 41), 10)
    assert QualityWarning.BLUR_DETECTED in ImageQualityAssessor().assess(blurred, bbox=bbox, candidate_mask=mask).warnings

    _, mask, _ = candidate_image(180, 10)
    shifted_mask = np.zeros_like(mask)
    cv2.ellipse(shifted_mask, (25, 200), (60, 100), 0, 0, 360, 255, -1)
    assert QualityWarning.BORDER_CLIPPED in ImageQualityAssessor().assess(image, bbox=(0, 100, 85, 200), candidate_mask=shifted_mask).warnings


def test_detector_returns_no_confidence() -> None:
    image, _, _ = candidate_image(180, 10)
    result = EggDetector().detect(image)
    assert result.confidence is None
