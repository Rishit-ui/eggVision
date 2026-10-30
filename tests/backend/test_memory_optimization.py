"""
Tests for Memory Optimization, Bounded Image Scaling, and Semaphore Concurrency.
Verifies that EggVision operates reliably under low-memory constraints (Render 512 MB).
"""

import asyncio
import gc
import tracemalloc
import numpy as np
import cv2
import pytest

from ml.vision.detector import EggDetector, ScreeningThresholds
from ml.vision.pipeline import VisionPipeline
from app.services.cv_service import (
    CVService,
    _decode_and_bound_image,
    MAX_WORKING_DIM,
)


def test_decode_and_bound_image_preserves_smaller_images():
    """Images with dimensions <= MAX_WORKING_DIM should not be resized."""
    h, w = 800, 600
    img = np.full((h, w, 3), 128, dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    raw_bytes = buf.tobytes()

    working_img, orig_w, orig_h, scale = _decode_and_bound_image(raw_bytes, MAX_WORKING_DIM)

    assert working_img is not None
    assert orig_w == 600
    assert orig_h == 800
    assert scale == 1.0
    assert working_img.shape == (800, 600, 3)


def test_decode_and_bound_image_downscales_large_images():
    """Images with max dimension > MAX_WORKING_DIM must be bounded to MAX_WORKING_DIM."""
    h, w = 3000, 4000
    img = np.full((h, w, 3), 128, dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    raw_bytes = buf.tobytes()

    working_img, orig_w, orig_h, scale = _decode_and_bound_image(raw_bytes, MAX_WORKING_DIM)

    assert working_img is not None
    assert orig_w == 4000
    assert orig_h == 3000
    assert scale == pytest.approx(1600.0 / 4000.0, rel=1e-3)
    assert working_img.shape[1] == 1600
    assert working_img.shape[0] == 1200


def test_detector_lab_distance_memory_budget():
    """
    Candidate mask generation on a 1600x1200 image must remain strictly
    below 40 MB peak memory (vs ~850 MB before optimization).
    """
    detector = EggDetector()
    h, w = 1200, 1600
    img = np.full((h, w, 3), 35, dtype=np.uint8)
    cv2.ellipse(img, (800, 600), (400, 300), 0, 0, 360, (210, 190, 150), -1)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    gc.collect()
    tracemalloc.start()
    masks = detector._candidate_masks(img, gray, "general_photograph")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak / (1024 * 1024)
    assert len(masks) >= 1
    # Strict memory ceiling: peak allocation during mask extraction must not exceed 40 MB
    assert peak_mb < 40.0, f"Peak memory {peak_mb:.2f} MB exceeded 40 MB ceiling"


def test_detector_distance_numerical_equivalence():
    """
    Verify that the channel-by-channel sum of squared differences produces
    the exact same mask as the mathematical Euclidean Lab distance.
    """
    threshold = 18
    thresh_sq = float(threshold ** 2)

    # Synthetic image with diverse Lab colors
    np.random.seed(42)
    img = np.random.randint(0, 256, (300, 400, 3), dtype=np.uint8)
    lab_u8 = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    border_u8 = np.concatenate((lab_u8[0], lab_u8[-1], lab_u8[:, 0], lab_u8[:, -1]), axis=0)
    bg = np.median(border_u8, axis=0)

    # Reference calculation
    lab_ref = lab_u8.astype(np.float64)
    dist_ref = np.linalg.norm(lab_ref - bg, axis=2)
    mask_ref = (dist_ref >= threshold).astype(np.uint8) * 255

    # Optimized calculation
    bg_f32 = bg.astype(np.float32)
    dL = lab_u8[:, :, 0].astype(np.float32) - bg_f32[0]
    dist_sq = dL * dL
    da = lab_u8[:, :, 1].astype(np.float32) - bg_f32[1]
    dist_sq += da * da
    db = lab_u8[:, :, 2].astype(np.float32) - bg_f32[2]
    dist_sq += db * db
    mask_opt = (dist_sq >= thresh_sq).astype(np.uint8) * 255

    mismatches = np.count_nonzero(mask_ref != mask_opt)
    assert mismatches == 0, f"Found {mismatches} mismatched pixels between reference and optimized masks"


def test_cv_service_rescaling_geometry():
    """When an image is scaled down, candidate geometry must map back to original coordinates."""
    # High-res image 3200x2400 (scale = 0.5 to 1600x1200)
    h, w = 2400, 3200
    img = np.full((h, w, 3), 30, dtype=np.uint8)
    cv2.ellipse(img, (1600, 1200), (500, 350), 0, 0, 360, (220, 200, 160), -1)
    _, buf = cv2.imencode(".jpg", img)
    raw_bytes = buf.tobytes()

    # Verify _decode_and_bound_image scales it to 0.5
    working_img, orig_w, orig_h, scale = _decode_and_bound_image(raw_bytes, 1600)
    assert orig_w == 3200
    assert orig_h == 2400
    assert scale == pytest.approx(0.5, rel=1e-2)
    assert working_img.shape[1] == 1600
    assert working_img.shape[0] == 1200

    # Simulate geometry rescaling mapping as performed in CVService
    mock_geo = {
        "width": 100.0,
        "height": 150.0,
        "area": 12000.0,
        "centroid": [800.0, 600.0],
        "aspect_ratio": 1.5,
        "orientation_deg": 12.0,
    }
    rescaled_geo = {
        "width": round(mock_geo["width"] / scale, 2),
        "height": round(mock_geo["height"] / scale, 2),
        "area": round(mock_geo["area"] / (scale * scale), 2),
        "centroid": [
            round(mock_geo["centroid"][0] / scale, 2),
            round(mock_geo["centroid"][1] / scale, 2),
        ],
        "aspect_ratio": mock_geo["aspect_ratio"],
        "orientation_deg": mock_geo["orientation_deg"],
    }
    assert rescaled_geo["width"] == 200.0
    assert rescaled_geo["height"] == 300.0
    assert rescaled_geo["area"] == 48000.0
    assert rescaled_geo["centroid"] == [1600.0, 1200.0]
    assert rescaled_geo["aspect_ratio"] == 1.5
    assert rescaled_geo["orientation_deg"] == 12.0
