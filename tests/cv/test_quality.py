"""Tests for Image Quality Module."""

import cv2
import numpy as np
import pytest
from ml.vision.quality import ImageQualityAssessor, QualityWarning
from ml.vision.detector import EggDetector


def create_synthetic_candled_egg(h=400, w=300, offset_x=0, offset_y=0, blur_sigma=0) -> np.ndarray:
    """Generate a synthetic intact candled egg in a dark chamber."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    center = (w // 2 + offset_x, h // 2 + offset_y)
    axes = (65, 100)
    
    # Draw warm glowing egg interior (amber/orange-yellow glow in BGR)
    # Background stays dark (5, 5, 8)
    img[:] = [10, 10, 15]
    
    # Draw shell glow with internal gradient
    cv2.ellipse(img, center, axes, 0, 0, 360, (40, 140, 230), -1)
    # Inner brighter yolk/light zone
    cv2.ellipse(img, (center[0], center[1] + 10), (45, 65), 0, 0, 360, (70, 180, 255), -1)

    # Add realistic shell texture / fine noise
    noise = np.random.normal(0, 5, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    if blur_sigma > 0:
        ksize = int(blur_sigma * 6) | 1
        img = cv2.GaussianBlur(img, (ksize, ksize), blur_sigma)

    return img


def test_good_image_quality():
    img = create_synthetic_candled_egg()
    detector = EggDetector()
    det = detector.detect(img)
    assert det.found is True

    assessor = ImageQualityAssessor()
    report = assessor.assess(img, bbox=det.bbox, has_egg=det.found)

    assert report.image_quality in ["GOOD", "ACCEPTABLE"]
    assert report.quality_score >= 0.70
    assert report.retake_recommended is False
    assert QualityWarning.BLUR_DETECTED not in report.warnings


def test_blurred_image_quality():
    img = create_synthetic_candled_egg(blur_sigma=12.0)
    assessor = ImageQualityAssessor()
    report = assessor.assess(img, has_egg=True)

    assert QualityWarning.BLUR_DETECTED in report.warnings
    assert report.metrics["laplacian_variance"] < 100.0


def test_overexposed_image_quality():
    # Saturated white image
    img = np.full((300, 300, 3), 253, dtype=np.uint8)
    assessor = ImageQualityAssessor()
    report = assessor.assess(img, has_egg=False)

    assert QualityWarning.OVEREXPOSED in report.warnings
    assert report.image_quality == "POOR"
    assert report.retake_recommended is True


def test_underexposed_image_quality():
    # Pitch black image
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    assessor = ImageQualityAssessor()
    report = assessor.assess(img, has_egg=False)

    assert QualityWarning.UNDEREXPOSED in report.warnings
    assert report.image_quality == "POOR"
    assert report.retake_recommended is True


def test_border_clipped_egg():
    # Egg positioned right at the frame edge
    img = create_synthetic_candled_egg(h=300, w=300, offset_x=120)  # Clipped against right border
    detector = EggDetector()
    det = detector.detect(img)

    assessor = ImageQualityAssessor()
    report = assessor.assess(img, bbox=det.bbox, has_egg=det.found)
    assert QualityWarning.BORDER_CLIPPED in report.warnings
