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
    assert "MULTIPLE_CANDIDATES" in result.quality.warnings
    assert result.quality.retake_recommended is True


def test_single_candidate_contour_abstains_without_a_validated_detector():
    image = np.full((400, 400, 3), (10, 10, 15), dtype=np.uint8)
    cv2.ellipse(image, (200, 200), (70, 120), 0, 0, 360, (40, 140, 230), -1)

    result = VisionPipeline().process(image)
    evidence = result.to_dict()["analysis"]

    assert result.detection.found is True
    assert result.detection.confidence is None
    assert result.detection.status == "UNCERTAIN"
    assert result.can_proceed_to_inference is False
    assert evidence["status"] == "UNCERTAIN"
    assert evidence["model"]["validated_egg_detector"] is False
    assert "candidate_geometry" in result.to_dict()
    assert "geometry" not in result.to_dict()
