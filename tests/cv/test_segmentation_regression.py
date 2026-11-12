"""Regression tests for egg segmentation defect fix and multi-background screening."""

import cv2
import numpy as np
import pytest

from ml.vision.pipeline import VisionPipeline
from ml.vision.quality import ImageQualityAssessor, QualityWarning
from ml.vision.segmentation import EggSegmenter


def create_fused_egg_image(h=600, w=800) -> tuple[np.ndarray, np.ndarray]:
    """
    Reproduces the exact production failure:
    A brown egg with a bright white light flare / reflection attached to its right side.
    """
    img = np.full((h, w, 3), (30, 30, 35), dtype=np.uint8)
    # Brown egg
    cv2.ellipse(img, (360, 300), (95, 145), 0, 0, 360, (40, 130, 200), -1)
    # White glare attached to right side
    cv2.ellipse(img, (470, 305), (35, 75), 0, 0, 360, (245, 248, 252), -1)
    # Connecting bridge
    cv2.rectangle(img, (430, 280), (470, 330), (230, 240, 250), -1)

    # Old naive candidate mask that included both
    naive_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(naive_mask, (360, 300), (95, 145), 0, 0, 360, 255, -1)
    cv2.ellipse(naive_mask, (470, 305), (35, 75), 0, 0, 360, 255, -1)
    cv2.rectangle(naive_mask, (430, 280), (470, 330), 255, -1)

    return img, naive_mask


def test_segmentation_prunes_attached_white_region():
    """Verify that the corrected segmenter prunes the attached white glare."""
    img, naive_mask = create_fused_egg_image()

    segmenter = EggSegmenter()
    contours, _ = cv2.findContours(naive_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    hint_cnt = max(contours, key=cv2.contourArea)

    res = segmenter.segment(img, contour_hint=hint_cnt)
    assert res.success is True
    assert res.status == "VALID_CANDIDATE"

    # Verify that white pixels on the right are excluded from the corrected mask
    corrected_mask = res.mask
    white_pixels_in_mask = np.sum((corrected_mask > 0) & (img[:, :, 0] > 200) & (img[:, :, 1] > 200) & (img[:, :, 2] > 200))
    assert white_pixels_in_mask < 50, f"Expected white region pruned, but found {white_pixels_in_mask} white pixels"

    # Verify egg morphometry is established
    geo = res.geometry
    assert geo.area > 20000
    assert 1.2 <= geo.aspect_ratio <= 1.8
    assert geo.solidity >= 0.90


def test_normalized_image_excludes_white_region():
    """Verify that the end-to-end pipeline produces a clean normalized image without the white blob."""
    img, _ = create_fused_egg_image()
    pipeline = VisionPipeline()
    res = pipeline.process(img)

    assert res.segmentation is not None
    assert res.segmentation.status == "VALID_CANDIDATE"
    assert res.normalization is not None
    assert res.normalization.success is True

    norm = res.normalization.normalized_image
    assert norm.shape == (512, 512, 3)

    # In canonical 512x512 normalized frame, background is black [0,0,0]
    # Check that right quadrant has no white glare
    right_quadrant = norm[:, 256:]
    white_in_norm = np.sum((right_quadrant[:, :, 0] > 220) & (right_quadrant[:, :, 1] > 220) & (right_quadrant[:, :, 2] > 220))
    assert white_in_norm < 50


@pytest.mark.parametrize(
    "bg_name,bg_bgr,shell_bgr",
    [
        ("dark_chamber", (20, 20, 25), (40, 130, 200)),     # Condition 1: Dark candling
        ("blue_surface", (180, 110, 40), (45, 135, 205)),   # Condition 2: Blue background
        ("neutral_grey", (128, 128, 128), (40, 130, 200)),  # Condition 3: Medium grey
        ("wood_surface", (45, 85, 140), (210, 220, 230)),   # Condition 4: Wooden surface with white egg
        ("light_matte", (215, 215, 215), (40, 130, 200)),   # Condition 5: Light matte background
    ],
)
def test_five_background_conditions(bg_name: str, bg_bgr: tuple, shell_bgr: tuple):
    """Verify screening and segmentation across five distinct background conditions."""
    h, w = 600, 800
    img = np.full((h, w, 3), bg_bgr, dtype=np.uint8)
    cv2.ellipse(img, (400, 300), (95, 145), 0, 0, 360, shell_bgr, -1)

    pipeline = VisionPipeline()
    res = pipeline.process(img)

    assert res.detection.found is True, f"Detection failed on background {bg_name}"
    assert res.detection.status == "UNCERTAIN"  # No fabricated detector confidence
    assert res.quality.image_quality in ["GOOD", "ACCEPTABLE"]
    assert res.segmentation is not None
    assert res.segmentation.status == "VALID_CANDIDATE"
    assert res.segmentation.geometry.area > 20000


def test_sharpness_screening_independent_of_egg_detection():
    """Verify sharpness is computed even when no egg candidate is detected."""
    # Blank out-of-focus blurred image without egg
    blank_blurred = np.full((400, 400, 3), 128, dtype=np.uint8)
    blank_blurred = cv2.GaussianBlur(blank_blurred, (41, 41), 10.0)

    report = ImageQualityAssessor().assess(blank_blurred)
    assert "frame_laplacian_variance" in report.metrics
    assert QualityWarning.EXPOSURE_INCONCLUSIVE in report.warnings


def test_ui_limitation_text_tailored_to_capture_mode():
    """Verify general photograph mode does NOT mention chamber silhouette."""
    # General photo mode (light border)
    light_img = np.full((500, 500, 3), 200, dtype=np.uint8)
    cv2.ellipse(light_img, (250, 250), (80, 120), 0, 0, 360, (40, 130, 200), -1)

    res_gen = VisionPipeline().process(light_img)
    assert res_gen.detection.capture_mode == "general_photograph"
    dict_gen = res_gen.to_dict()
    limitations = " ".join(dict_gen["analysis"]["limitations"])
    assert "chamber silhouette" not in limitations
    assert "candidate contour is an optical shape observation" in limitations
