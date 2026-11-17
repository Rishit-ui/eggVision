"""EggVision AI — ONNX NMS Parity and Coordinate Decoding Regression Tests.

Verifies exact parity and robustness of the ONNX postprocessing pipeline:
- Square aspect-ratio preserving letterboxing
- NMS suppression in 640x640 letterbox coordinate space
- Post-NMS inverse letterbox coordinate mapping
- Image boundary clipping
- Deterministic sorting by confidence descending
- Max detection limits
- Support for diverse tensor input shapes
"""

import json
from pathlib import Path

import numpy as np
import pytest

from ml.inference.onnx_postprocess import decode_and_nms_yolov8, letterbox_image


class TestLetterboxImage:
    """Test image letterboxing transformations."""

    def test_square_image_letterbox(self):
        img = np.zeros((640, 640, 3), dtype=np.uint8)
        lb, scale, (left, top) = letterbox_image(img, target_size=640)
        assert lb.shape == (640, 640, 3)
        assert scale == 1.0
        assert left == 0
        assert top == 0

    def test_landscape_image_letterbox(self):
        img = np.zeros((300, 600, 3), dtype=np.uint8)
        lb, scale, (left, top) = letterbox_image(img, target_size=640)
        assert lb.shape == (640, 640, 3)
        assert scale == pytest.approx(640 / 600, rel=1e-3)
        assert left == 0
        assert top > 0  # vertical padding added
        # Check border fill color is 114
        assert lb[0, 0, 0] == 114

    def test_portrait_image_letterbox(self):
        img = np.zeros((800, 400, 3), dtype=np.uint8)
        lb, scale, (left, top) = letterbox_image(img, target_size=640)
        assert lb.shape == (640, 640, 3)
        assert scale == pytest.approx(640 / 800, rel=1e-3)
        assert left > 0  # horizontal padding added
        assert top == 0
        assert lb[0, 0, 0] == 114


class TestDecodeAndNmsYolov8:
    """Test YOLOv8 coordinate decoding, filtering, and NMS suppression."""

    def test_empty_raw_predictions(self):
        raw = np.zeros((1, 5, 0), dtype=np.float32)
        boxes, scores = decode_and_nms_yolov8(raw, orig_shape=(1000, 1000), pad_info=(0, 0), scale=0.64)
        assert boxes == []
        assert scores == []

    def test_confidence_threshold_filtering(self):
        # 3 boxes: scores 0.10, 0.24, 0.85
        # Format: [cx, cy, w, h, score]
        preds = np.array([
            [100.0, 100.0, 50.0, 50.0, 0.10],
            [200.0, 200.0, 50.0, 50.0, 0.24],
            [300.0, 300.0, 50.0, 50.0, 0.85],
        ], dtype=np.float32)
        boxes, scores = decode_and_nms_yolov8(
            preds, orig_shape=(640, 640), pad_info=(0, 0), scale=1.0, conf_threshold=0.25
        )
        assert len(boxes) == 1
        assert len(scores) == 1
        assert scores[0] == pytest.approx(0.85, rel=1e-3)

    def test_nms_suppression_in_letterbox_space(self):
        # 2 overlapping boxes at same location, different scores
        preds = np.array([
            [320.0, 320.0, 100.0, 100.0, 0.90],
            [322.0, 321.0, 98.0, 99.0, 0.80],  # high IoU with above box
        ], dtype=np.float32)
        boxes, scores = decode_and_nms_yolov8(
            preds, orig_shape=(640, 640), pad_info=(0, 0), scale=1.0, conf_threshold=0.25, iou_threshold=0.50
        )
        assert len(boxes) == 1
        assert scores[0] == 0.90

    def test_coordinate_inversion_and_boundary_clipping(self):
        # Simulated box near the image edge that partially extends into padding
        orig_w, orig_h = 400, 300
        target = 640
        scale = min(target / orig_h, target / orig_w)  # 640 / 400 = 1.6
        nw, nh = int(round(orig_w * scale)), int(round(orig_h * scale))
        pad_x = (target - nw) / 2
        pad_y = (target - nh) / 2

        # A box positioned near the top edge in letterbox space
        # cx = 320, cy = pad_y, w = 100, h = 100 -> extends above pad_y into letterbox padding
        preds = np.array([
            [320.0, pad_y, 100.0, 100.0, 0.95],
        ], dtype=np.float32)

        boxes, scores = decode_and_nms_yolov8(
            preds, orig_shape=(orig_h, orig_w), pad_info=(int(pad_x), int(pad_y)), scale=scale, conf_threshold=0.25
        )
        assert len(boxes) == 1
        x1, y1, x2, y2 = boxes[0]
        # y1 must be clipped to 0.0 (top edge of original image)
        assert y1 >= 0.0
        assert y2 <= orig_h
        assert x1 >= 0.0
        assert x2 <= orig_w

    def test_max_det_limit(self):
        # 10 non-overlapping boxes
        preds = []
        for i in range(10):
            preds.append([50.0 + i * 50.0, 50.0 + i * 50.0, 20.0, 20.0, 0.50 + i * 0.04])
        preds_arr = np.array(preds, dtype=np.float32)

        boxes, scores = decode_and_nms_yolov8(
            preds_arr, orig_shape=(640, 640), pad_info=(0, 0), scale=1.0, conf_threshold=0.25, max_det=3
        )
        assert len(boxes) == 3
        assert len(scores) == 3
        # Should be the 3 highest scores in descending order
        assert scores[0] >= scores[1] >= scores[2]

    def test_3d_tensor_input_shape_transposition(self):
        # Standard YOLOv8 ONNX shape: [1, 5, 8400]
        tensor = np.zeros((1, 5, 8400), dtype=np.float32)
        tensor[0, 0, 10] = 320.0  # cx
        tensor[0, 1, 10] = 320.0  # cy
        tensor[0, 2, 10] = 80.0   # bw
        tensor[0, 3, 10] = 80.0   # bh
        tensor[0, 4, 10] = 0.92   # score

        boxes, scores = decode_and_nms_yolov8(
            tensor, orig_shape=(480, 640), pad_info=(0, 80), scale=1.0, conf_threshold=0.25
        )
        assert len(boxes) == 1
        assert scores[0] == 0.92


class TestEquivalenceReportParity:
    """Verify that the generated ONNX equivalence report achieves required parity."""

    def test_equivalence_report_matches_27_of_27(self):
        report_path = Path("ml/artifacts/detection/onnx_equivalence_report.json")
        assert report_path.exists(), "Equivalence report file must exist"
        report = json.loads(report_path.read_text(encoding="utf-8"))

        assert report["status"] == "PASSED_EQUIVALENT"
        summary = report["summary"]
        assert summary["total_images"] == 27
        assert summary["count_matches"] == 27
        assert summary["total_box_pairs"] == 172
        assert summary["mean_iou"] >= 0.90
        assert summary["mean_confidence_diff"] <= 0.03
