"""EggVision AI — ONNX Runtime Postprocessing & Coordinate Decoding.

Reusable, lightweight postprocessing pipeline for YOLOv8 ONNX models.
Implements letterbox coordinate transformation, confidence filtering,
Non-Maximum Suppression (NMS) in normalized letterbox space, coordinate
inversion, and boundary clipping.
"""

from typing import Any

import cv2
import numpy as np


def letterbox_image(
    image: np.ndarray,
    target_size: int = 640,
) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize image to square target size with aspect-ratio preserving padding.

    Args:
        image: Source image array in HWC format (e.g. BGR or RGB).
        target_size: Target square dimension (width and height), default 640.

    Returns:
        tuple containing:
            - letterboxed: Padded square image of shape (target_size, target_size, C).
            - scale: Scale factor applied to original image dimensions.
            - (left, top): Padding offsets (left, top) in pixels.
    """
    h, w = image.shape[:2]
    scale = min(target_size / h, target_size / w)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    pad_x = (target_size - nw) / 2
    pad_y = (target_size - nh) / 2
    top = int(round(pad_y - 0.1))
    bottom = int(round(pad_y + 0.1))
    left = int(round(pad_x - 0.1))
    right = int(round(pad_x + 0.1))

    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)
    letterboxed = cv2.copyMakeBorder(
        resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
    )
    return letterboxed, scale, (left, top)


def decode_and_nms_yolov8(
    raw_preds: np.ndarray,
    orig_shape: tuple[int, int] | list[int],
    pad_info: tuple[int, int],
    scale: float,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.50,
    max_det: int = 300,
    box_precision: int = 1,
) -> tuple[list[list[float]], list[float]]:
    """Decode YOLOv8 output tensor and apply NMS with exact coordinate order.

    Pipeline:
    1. Squeeze and format raw output to [N, 5] (cx, cy, w, h, score).
    2. Filter candidates by confidence threshold.
    3. Convert center coordinates to top-left corner coordinates in 640x640
       letterbox space (xywh format required by cv2.dnn.NMSBoxes).
    4. Apply Non-Maximum Suppression in letterbox space BEFORE scaling or clipping.
    5. Reverse letterbox transform (subtract padding, divide by scale) to recover
       original image coordinates.
    6. Clip surviving boxes to original image boundaries [0, orig_w] and [0, orig_h].
    7. Order detections deterministically by confidence descending.

    Args:
        raw_preds: Output tensor array of shape [1, 5, 8400] or [8400, 5].
        orig_shape: Original image dimensions (height, width).
        pad_info: Padding offsets (left, top) added during letterboxing.
        scale: Scale factor used during letterboxing.
        conf_threshold: Minimum confidence score to consider.
        iou_threshold: Intersection over Union threshold for NMS suppression.
        max_det: Maximum number of surviving detections to return.
        box_precision: Decimal places for rounding bounding box coordinates.

    Returns:
        tuple containing:
            - detected_boxes: List of [x1, y1, x2, y2] bounding boxes in original pixels.
            - detected_scores: List of confidence scores corresponding to boxes.
    """
    preds: np.ndarray = np.asarray(raw_preds)
    if preds.ndim == 3:
        # [1, 5, 8400] -> [8400, 5] or [1, 8400, 5] -> [8400, 5]
        preds = np.squeeze(preds, axis=0).T if preds.shape[1] == 5 else np.squeeze(preds, axis=0)
    elif preds.ndim == 2 and preds.shape[0] == 5 and preds.shape[1] != 5:
        preds = preds.T

    if preds.size == 0 or preds.shape[0] == 0:
        return [], []

    orig_h, orig_w = orig_shape[0], orig_shape[1]
    left, top = pad_info

    scores = preds[:, 4]
    mask = scores >= conf_threshold
    filtered_preds = preds[mask]
    filtered_scores = scores[mask]

    if len(filtered_preds) == 0:
        return [], []

    cx = filtered_preds[:, 0]
    cy = filtered_preds[:, 1]
    bw = filtered_preds[:, 2]
    bh = filtered_preds[:, 3]

    # Letterbox coordinates: top-left x, top-left y, width, height
    x1_lb = cx - bw / 2.0
    y1_lb = cy - bh / 2.0

    boxes_lb: list[list[float]] = [
        [float(x1_lb[i]), float(y1_lb[i]), float(bw[i]), float(bh[i])]
        for i in range(len(filtered_preds))
    ]

    indices: Any = cv2.dnn.NMSBoxes(
        boxes_lb,
        filtered_scores.tolist(),
        score_threshold=float(conf_threshold),
        nms_threshold=float(iou_threshold),
        top_k=int(max_det),
    )

    if len(indices) == 0:
        return [], []

    flat_indices = np.array(indices).flatten()[:max_det]

    detected_boxes: list[list[float]] = []
    detected_scores: list[float] = []

    for idx in flat_indices:
        i = int(idx)
        # Reverse letterbox transform
        x1_val = (cx[i] - bw[i] / 2.0 - left) / scale
        y1_val = (cy[i] - bh[i] / 2.0 - top) / scale
        x2_val = (cx[i] + bw[i] / 2.0 - left) / scale
        y2_val = (cy[i] + bh[i] / 2.0 - top) / scale

        # Clip surviving boxes to original image boundaries
        x1_clipped = max(0.0, min(float(orig_w), float(x1_val)))
        y1_clipped = max(0.0, min(float(orig_h), float(y1_val)))
        x2_clipped = max(0.0, min(float(orig_w), float(x2_val)))
        y2_clipped = max(0.0, min(float(orig_h), float(y2_val)))

        detected_boxes.append([
            round(x1_clipped, box_precision),
            round(y1_clipped, box_precision),
            round(x2_clipped, box_precision),
            round(y2_clipped, box_precision),
        ])
        detected_scores.append(round(float(filtered_scores[i]), 4))

    return detected_boxes, detected_scores
