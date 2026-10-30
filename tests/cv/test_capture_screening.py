"""Synthetic behavioral tests for non-ML capture screening.

These fixtures test only deterministic contour/optics behavior; they do not
claim real-world egg-detection accuracy.
"""

import cv2
import numpy as np

from ml.vision.detector import EggDetector
from ml.vision.pipeline import VisionPipeline
from ml.vision.quality import ImageQualityAssessor, QualityWarning


def subject(background: tuple[int, int, int], shell: tuple[int, int, int], center=(200, 200), axes=(65, 105), size=(400, 400)) -> np.ndarray:
    image = np.full((size[0], size[1], 3), background, dtype=np.uint8)
    cv2.ellipse(image, center, axes, 0, 0, 360, shell, -1)
    cv2.ellipse(image, (center[0] - 14, center[1] - 10), (20, 38), 0, 0, 360, tuple(min(255, value + 25) for value in shell), -1)
    return image


def test_white_background_subject_is_screened_without_overexposure() -> None:
    image = subject((245, 245, 245), (120, 165, 205))
    result = VisionPipeline().process(image)
    assert result.detection.found is True
    assert result.detection.capture_mode == "general_photograph"
    assert QualityWarning.OVEREXPOSED not in result.quality.warnings
    assert result.quality.metrics["exposure_region"] == "candidate_roi"


def test_dark_and_neutral_backgrounds_are_supported() -> None:
    for background, shell in [((12, 12, 16), (40, 140, 230)), ((128, 128, 128), (75, 125, 180))]:
        result = EggDetector().detect(subject(background, shell))
        assert result.found is True
        assert result.status == "UNCERTAIN"


def test_bright_candidate_on_dark_background_is_not_whole_frame_overexposure() -> None:
    result = VisionPipeline().process(subject((10, 10, 10), (245, 245, 245)))
    assert result.detection.found
    assert QualityWarning.OVEREXPOSED in result.quality.warnings


def test_uniform_white_background_without_candidate_is_inconclusive() -> None:
    result = VisionPipeline().process(np.full((400, 400, 3), 245, dtype=np.uint8))
    assert result.detection.status == "UNSUPPORTED_BACKGROUND"
    assert QualityWarning.EXPOSURE_INCONCLUSIVE in result.quality.warnings
    assert result.quality.quality_score is None


def test_multiple_candidates_are_distinguished() -> None:
    image = np.full((400, 400, 3), (20, 20, 20), dtype=np.uint8)
    cv2.ellipse(image, (110, 200), (52, 86), 0, 0, 360, (60, 150, 220), -1)
    cv2.ellipse(image, (290, 200), (52, 86), 0, 0, 360, (60, 150, 220), -1)
    result = VisionPipeline().process(image)
    assert result.detection.status == "MULTIPLE_CANDIDATES"
    assert QualityWarning.MULTIPLE_CANDIDATES in result.quality.warnings


def test_blur_shadows_framing_and_low_resolution_are_reported() -> None:
    blurred = cv2.GaussianBlur(subject((20, 20, 20), (50, 150, 220)), (41, 41), 10)
    assert QualityWarning.BLUR_DETECTED in VisionPipeline().process(blurred).quality.warnings

    shadowed = subject((25, 25, 25), (50, 150, 220))
    cv2.ellipse(shadowed, (165, 200), (30, 82), 0, 0, 360, (30, 35, 40), -1)
    mask = np.zeros(shadowed.shape[:2], dtype=np.uint8)
    cv2.ellipse(mask, (200, 200), (65, 105), 0, 0, 360, 255, -1)
    report = ImageQualityAssessor().assess(shadowed, bbox=(135, 95, 130, 210), candidate_mask=mask)
    assert QualityWarning.STRONG_SHADOWS in report.warnings

    partial = subject((20, 20, 20), (50, 150, 220), center=(30, 200))
    assert QualityWarning.BORDER_CLIPPED in VisionPipeline().process(partial).quality.warnings

    small = subject((20, 20, 20), (50, 150, 220), center=(60, 60), axes=(22, 37), size=(120, 120))
    assert QualityWarning.LOW_RESOLUTION in VisionPipeline().process(small).quality.warnings


def test_empty_and_invalid_inputs_are_not_candidates() -> None:
    assert EggDetector().detect(np.array([], dtype=np.uint8)).status == "INVALID_IMAGE"
    assert VisionPipeline().process(np.array([], dtype=np.uint8)).detection.status == "INVALID_IMAGE"
