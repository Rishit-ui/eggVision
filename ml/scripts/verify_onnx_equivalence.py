"""EggVision AI — PyTorch vs ONNX Inference Equivalence Verification.

Runs the original PyTorch YOLOv8n detector and exported ONNX model across a fixed set
of validation images. Computes detection count parity, box coordinate IoU, confidence
divergence, and inference latency speedup.
"""

import argparse
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("verify_equivalence")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PT_WEIGHTS = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "best.pt"
DEFAULT_ONNX_WEIGHTS = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "eggvision_detector.onnx"
DEFAULT_IMAGES_DIR = REPO_ROOT / "ml" / "data" / "processed" / "egg_detection_yolo" / "images" / "val"
DEFAULT_REPORT_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "onnx_equivalence_report.json"


def letterbox_image(image: np.ndarray, target_size: int = 640) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Letterbox resize image to target static square while preserving aspect ratio."""
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


def run_onnx_inference(
    session: Any,
    image: np.ndarray,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.70,
    target_size: int = 640,
) -> tuple[list[list[float]], list[float], float]:
    """Run ONNX detector with letterboxing, decoding, and NMS."""
    h, w = image.shape[:2]
    letterboxed, scale, (left, top) = letterbox_image(image, target_size)

    # Preprocess: BGR -> RGB, float32, normalize [0, 1], transpose to BCHW
    blob = letterboxed[:, :, ::-1].astype(np.float32) / 255.0
    blob = np.transpose(blob, (2, 0, 1))[None, ...]

    t0 = time.perf_counter()
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: blob})
    latency_ms = (time.perf_counter() - t0) * 1000.0

    raw_preds = np.squeeze(outputs[0]).T  # shape: [8400, 5]
    scores = raw_preds[:, 4]
    mask = scores >= conf_threshold
    filtered_boxes = raw_preds[mask]
    filtered_scores = scores[mask]

    if len(filtered_boxes) == 0:
        return [], [], latency_ms

    cx = filtered_boxes[:, 0]
    cy = filtered_boxes[:, 1]
    bw = filtered_boxes[:, 2]
    bh = filtered_boxes[:, 3]

    x1 = np.clip((cx - bw / 2 - left) / scale, 0, w)
    y1 = np.clip((cy - bh / 2 - top) / scale, 0, h)
    x2 = np.clip((cx + bw / 2 - left) / scale, 0, w)
    y2 = np.clip((cy + bh / 2 - top) / scale, 0, h)

    cv_boxes = [
        [float(x1[i]), float(y1[i]), float(x2[i] - x1[i]), float(y2[i] - y1[i])]
        for i in range(len(x1))
    ]
    indices = cv2.dnn.NMSBoxes(
        cv_boxes, filtered_scores.tolist(), score_threshold=conf_threshold, nms_threshold=iou_threshold
    )

    boxes_out: list[list[float]] = []
    confs_out: list[float] = []
    flat_indices = np.array(indices).flatten() if len(indices) > 0 else []

    for idx in flat_indices:
        i = int(idx)
        boxes_out.append([round(float(x1[i]), 2), round(float(y1[i]), 2), round(float(x2[i]), 2), round(float(y2[i]), 2)])
        confs_out.append(round(float(filtered_scores[i]), 4))

    return boxes_out, confs_out, latency_ms


def compute_box_iou(boxA: list[float], boxB: list[float]) -> float:
    """Compute Intersection-over-Union between two [x1, y1, x2, y2] bounding boxes."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_w = max(0.0, xB - xA)
    inter_h = max(0.0, yB - yA)
    inter_area = inter_w * inter_h

    areaA = max(0.0, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
    areaB = max(0.0, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))
    union_area = areaA + areaB - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


def verify_equivalence(
    pt_path: Path,
    onnx_path: Path,
    images_dir: Path,
    conf_threshold: float = 0.25,
    min_mean_iou: float = 0.90,
    max_mean_conf_diff: float = 0.03,
) -> dict[str, Any]:
    """Compare PyTorch and ONNX predictions across image set."""
    import onnxruntime as ort
    from ultralytics import YOLO

    logger.info(f"Loading PyTorch model from {pt_path}...")
    pt_model = YOLO(str(pt_path))

    logger.info(f"Loading ONNX session from {onnx_path}...")
    onnx_session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    image_files = sorted(images_dir.glob("*.jpg")) + sorted(images_dir.glob("*.jpeg")) + sorted(images_dir.glob("*.png"))
    if not image_files:
        raise FileNotFoundError(f"No test images found in {images_dir}")

    logger.info(f"Evaluating equivalence across {len(image_files)} images from {images_dir.name}...")

    image_results: list[dict[str, Any]] = []
    all_ious: list[float] = []
    all_conf_diffs: list[float] = []
    pt_latencies: list[float] = []
    onnx_latencies: list[float] = []

    for img_path in image_files:
        img = cv2.imread(str(img_path))
        if img is None:
            continue

        # PyTorch inference
        t0 = time.perf_counter()
        pt_res = pt_model.predict(img, conf=conf_threshold, verbose=False)[0]
        pt_lat = (time.perf_counter() - t0) * 1000.0
        pt_latencies.append(pt_lat)

        pt_raw_boxes = pt_res.boxes.xyxy.cpu().numpy()
        pt_raw_confs = pt_res.boxes.conf.cpu().numpy()

        pt_boxes = [[round(float(v), 2) for v in b] for b in pt_raw_boxes]
        pt_confs = [round(float(c), 4) for c in pt_raw_confs]

        # ONNX inference
        onnx_boxes, onnx_confs, onnx_lat = run_onnx_inference(
            onnx_session, img, conf_threshold=conf_threshold
        )
        onnx_latencies.append(onnx_lat)

        # Pair boxes by best IoU
        matched_pairs: list[dict[str, Any]] = []
        unmatched_pt = list(range(len(pt_boxes)))
        unmatched_onnx = list(range(len(onnx_boxes)))

        for i, pt_b in enumerate(pt_boxes):
            best_iou = -1.0
            best_j = -1
            for j in unmatched_onnx:
                iou = compute_box_iou(pt_b, onnx_boxes[j])
                if iou > best_iou:
                    best_iou = iou
                    best_j = j

            if best_j >= 0 and best_iou >= 0.5:
                conf_diff = abs(pt_confs[i] - onnx_confs[best_j])
                matched_pairs.append({
                    "pt_box": pt_b,
                    "onnx_box": onnx_boxes[best_j],
                    "iou": round(best_iou, 4),
                    "pt_conf": pt_confs[i],
                    "onnx_conf": onnx_confs[best_j],
                    "conf_diff": round(conf_diff, 4),
                })
                all_ious.append(best_iou)
                all_conf_diffs.append(conf_diff)
                unmatched_onnx.remove(best_j)
                unmatched_pt.remove(i)

        count_match = len(pt_boxes) == len(onnx_boxes)
        image_results.append({
            "image": img_path.name,
            "pt_detection_count": len(pt_boxes),
            "onnx_detection_count": len(onnx_boxes),
            "count_matches": count_match,
            "matched_boxes": len(matched_pairs),
            "unmatched_pt_boxes": len(unmatched_pt),
            "unmatched_onnx_boxes": len(unmatched_onnx),
            "pt_latency_ms": round(pt_lat, 2),
            "onnx_latency_ms": round(onnx_lat, 2),
            "pairs": matched_pairs,
        })

    mean_iou = float(np.mean(all_ious)) if all_ious else 0.0
    mean_conf_diff = float(np.mean(all_conf_diffs)) if all_conf_diffs else 0.0
    max_conf_diff = float(np.max(all_conf_diffs)) if all_conf_diffs else 0.0
    min_iou = float(np.min(all_ious)) if all_ious else 0.0

    mean_pt_lat = float(np.mean(pt_latencies)) if pt_latencies else 0.0
    mean_onnx_lat = float(np.mean(onnx_latencies)) if onnx_latencies else 0.0
    speedup = round(mean_pt_lat / max(mean_onnx_lat, 0.001), 2)

    total_images = len(image_results)
    count_matches = sum(1 for r in image_results if r["count_matches"])

    passed = (
        mean_iou >= min_mean_iou
        and mean_conf_diff <= max_mean_conf_diff
        and count_matches == total_images
    )
    status = "PASSED_EQUIVALENT" if passed else "FAILED_DISCREPANCY"

    logger.info("=== Equivalence Summary ===")
    logger.info(f"  Images Evaluated: {total_images}")
    logger.info(f"  Detection Count Matches: {count_matches}/{total_images}")
    logger.info(f"  Total Box Pairs: {len(all_ious)}")
    logger.info(f"  Mean IoU: {mean_iou:.4f} (threshold >= {min_mean_iou})")
    logger.info(f"  Min IoU:  {min_iou:.4f}")
    logger.info(f"  Mean Conf Diff: {mean_conf_diff:.4f} (threshold <= {max_mean_conf_diff})")
    logger.info(f"  Max Conf Diff:  {max_conf_diff:.4f}")
    logger.info(f"  Mean PT Latency:   {mean_pt_lat:.2f} ms")
    logger.info(f"  Mean ONNX Latency: {mean_onnx_lat:.2f} ms")
    logger.info(f"  Speedup Factor:    {speedup}x")
    logger.info(f"  Verdict: {status}")

    return {
        "status": status,
        "verified_at": datetime.now(UTC).isoformat(),
        "summary": {
            "total_images": total_images,
            "count_matches": count_matches,
            "total_box_pairs": len(all_ious),
            "mean_iou": round(mean_iou, 4),
            "min_iou": round(min_iou, 4),
            "mean_confidence_diff": round(mean_conf_diff, 4),
            "max_confidence_diff": round(max_conf_diff, 4),
            "mean_pt_latency_ms": round(mean_pt_lat, 2),
            "mean_onnx_latency_ms": round(mean_onnx_lat, 2),
            "speedup_factor": speedup,
        },
        "acceptance_criteria": {
            "min_mean_iou": min_mean_iou,
            "max_mean_conf_diff": max_mean_conf_diff,
            "require_all_count_matches": True,
        },
        "images": image_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify PyTorch vs ONNX detector equivalence.")
    parser.add_argument("--pt-weights", type=Path, default=DEFAULT_PT_WEIGHTS)
    parser.add_argument("--onnx-weights", type=Path, default=DEFAULT_ONNX_WEIGHTS)
    parser.add_argument("--images-dir", type=Path, default=DEFAULT_IMAGES_DIR)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--conf", type=float, default=0.25)
    args = parser.parse_args()

    try:
        report = verify_equivalence(
            pt_path=args.pt_weights,
            onnx_path=args.onnx_weights,
            images_dir=args.images_dir,
            conf_threshold=args.conf,
        )

        args.output_report.parent.mkdir(parents=True, exist_ok=True)
        with args.output_report.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Equivalence report saved to {args.output_report}")

        if report["status"] != "PASSED_EQUIVALENT":
            logger.error("Equivalence check failed!")
            return 1
        return 0

    except Exception as e:
        logger.error(f"Verification script failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
