"""Regression tests for rejecting non-chamber and multi-egg inputs."""

import cv2
import numpy as np

from ml.vision.detector import EggDetector
from ml.vision.pipeline import VisionPipeline


def test_bright_full_frame_is_not_assumed_to_be_an_egg():
    image = np.full((320, 320, 3), 180, dtype=np.uint8)
    result = EggDetector().detect(image)
    assert result.found is False
    assert result.egg_count == 0


def test_multiple_isolated_eggs_block_pipeline_progression():
    image = np.full((400, 400, 3), (10, 10, 15), dtype=np.uint8)
    cv2.ellipse(image, (115, 200), (55, 90), 0, 0, 360, (40, 140, 230), -1)
    cv2.ellipse(image, (285, 200), (55, 90), 0, 0, 360, (40, 140, 230), -1)

    result = VisionPipeline().process(image)

    assert result.detection.egg_count > 1
    assert result.can_proceed_to_inference is False
    assert "MULTIPLE_EGGS_DETECTED" in result.quality.warnings
    assert result.quality.retake_recommended is True
