"""Tests for Egg Segmentation and Normalization Modules."""

import cv2
import numpy as np
from ml.vision.segmentation import EggSegmenter
from ml.vision.normalizer import EggNormalizer
from ml.vision.pipeline import VisionPipeline


def create_synthetic_candled_egg(h=400, w=300) -> np.ndarray:
    """Generate a clean synthetic intact candled egg in a dark chamber."""
    img = np.full((h, w, 3), (12, 12, 16), dtype=np.uint8)
    center = (w // 2, h // 2)
    axes = (60, 95)
    
    cv2.ellipse(img, center, axes, 0, 0, 360, (40, 140, 230), -1)
    cv2.ellipse(img, (center[0], center[1] + 10), (40, 60), 0, 0, 360, (60, 170, 250), -1)
    return img


def test_egg_segmentation():
    img = create_synthetic_candled_egg()
    segmenter = EggSegmenter()
    result = segmenter.segment(img)

    assert result.success is True
    assert result.mask.shape == (400, 300)
    assert np.unique(result.mask).tolist() == [0, 255]

    geo = result.geometry
    assert geo.area > 5000
    assert 1.2 <= geo.aspect_ratio <= 1.9
    assert abs(geo.centroid_x - 150) < 15
    assert abs(geo.centroid_y - 200) < 15


def test_egg_normalization():
    img = create_synthetic_candled_egg()
    segmenter = EggSegmenter()
    seg_res = segmenter.segment(img)

    normalizer = EggNormalizer(target_size=512)
    norm_res = normalizer.normalize(img, seg_res.mask, seg_res.geometry)

    assert norm_res.success is True
    assert norm_res.normalized_image.shape == (512, 512, 3)
    assert norm_res.normalized_mask.shape == (512, 512)
    assert norm_res.clahe_image.shape == (512, 512, 3)
    # Background outside egg mask should be zero
    assert norm_res.normalized_image[0, 0].tolist() == [0, 0, 0]


def test_vision_pipeline_end_to_end():
    img = create_synthetic_candled_egg()
    pipeline = VisionPipeline()
    res = pipeline.process(img)

    # A contour candidate is useful for normalization, but the current
    # heuristic is not a validated egg detector and must not unlock inference.
    assert res.can_proceed_to_inference is False
    assert res.detection.status == "UNCERTAIN"
    assert res.quality.image_quality in ["GOOD", "ACCEPTABLE"]
    assert res.detection.found is True
    assert res.segmentation is not None
    assert res.segmentation.success is True
    assert res.normalization is not None
    assert res.normalization.normalized_image.shape == (512, 512, 3)

    out_dict = res.to_dict()
    assert "image_quality" in out_dict
    assert "candidate_geometry" in out_dict
    assert out_dict["candidate_geometry"]["area"] > 5000
    assert out_dict["analysis"]["model"]["validated_egg_detector"] is False
