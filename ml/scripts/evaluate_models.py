#!/usr/bin/env python3
"""evaluate_models.py
EggVision ML Foundation — Model Evaluation and Scientific Validation Suite.

Evaluates trained egg detection model on the strictly held-out test split.
Computes mAP@0.50, mAP@0.50:0.95, Precision, Recall, F1 score, confusion matrix counts,
and detailed inference latency statistics (mean, median, p95).
Generates visual prediction plots on test images and outputs evaluation_report.json.
"""

import argparse
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("evaluate_models")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WEIGHTS = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "best.pt"
DEFAULT_DATA_YAML = REPO_ROOT / "ml" / "data" / "processed" / "egg_detection_yolo" / "data.yaml"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "ml" / "artifacts" / "detection"


def generate_sample_predictions_plot(
    model: Any,
    test_images: list[Path],
    output_path: Path,
    conf_threshold: float = 0.25,
    max_images: int = 6,
) -> None:
    """Generate a clean grid visualization of model predictions on test images."""
    selected_images = test_images[:max_images]
    if not selected_images:
        logger.warning("No test images available to generate prediction plot.")
        return

    n_cols = min(3, len(selected_images))
    n_rows = (len(selected_images) + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 5 * n_rows))
    if len(selected_images) == 1:
        axes = np.array([axes])
    axes = axes.flatten()

    for idx, img_path in enumerate(selected_images):
        results = model.predict(str(img_path), conf=conf_threshold, verbose=False)
        result = results[0]
        # result.plot() returns BGR image with drawn bboxes
        plotted_bgr = result.plot()
        plotted_rgb = cv2.cvtColor(plotted_bgr, cv2.COLOR_BGR2RGB)

        n_detected = len(result.boxes)
        ax = axes[idx]
        ax.imshow(plotted_rgb)
        ax.set_title(f"{img_path.name}\n({n_detected} eggs detected)", fontsize=11)
        ax.axis("off")

    # Hide any unused subplots
    for j in range(len(selected_images), len(axes)):
        axes[j].axis("off")

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    logger.info(f"Sample prediction plot saved to {output_path}")


def evaluate_detector(
    weights_path: Path = DEFAULT_WEIGHTS,
    data_yaml: Path = DEFAULT_DATA_YAML,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    conf_threshold: float = 0.25,
    iou_threshold: float = 0.50,
    device: str | None = None,
) -> dict[str, Any]:
    """Execute scientific evaluation on held-out test split."""
    from ultralytics import YOLO

    if not weights_path.exists():
        raise FileNotFoundError(f"Model weights not found at {weights_path}")
    if not data_yaml.exists():
        raise FileNotFoundError(f"Dataset configuration not found at {data_yaml}")

    if device is None:
        device = "0" if torch.cuda.is_available() else "cpu"

    logger.info(f"Loading YOLO detector from {weights_path} onto device={device}...")
    model = YOLO(str(weights_path))

    # 1. Run Ultralytics test-split validation
    logger.info("Executing validation on test split...")
    val_results = model.val(
        data=str(data_yaml.resolve().as_posix()),
        split="test",
        conf=conf_threshold,
        iou=iou_threshold,
        device=device,
        verbose=True,
    )

    box_metrics = val_results.box
    map50 = float(box_metrics.map50)
    map50_95 = float(box_metrics.map)
    precision = float(box_metrics.mp)
    recall = float(box_metrics.mr)
    f1 = 2 * (precision * recall) / (precision + recall + 1e-8)

    # 2. Measure inference latency across individual test images
    test_images_dir = data_yaml.parent / "images" / "test"
    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    test_images = sorted([p for p in test_images_dir.iterdir() if p.suffix.lower() in valid_exts])

    latencies_ms = []
    # Warmup
    if test_images:
        _ = model.predict(str(test_images[0]), conf=conf_threshold, device=device, verbose=False)

    for img_path in test_images:
        t0 = time.perf_counter()
        _ = model.predict(str(img_path), conf=conf_threshold, device=device, verbose=False)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    if latencies_ms:
        latency_stats = {
            "mean_ms": round(float(np.mean(latencies_ms)), 2),
            "median_ms": round(float(np.median(latencies_ms)), 2),
            "p95_ms": round(float(np.percentile(latencies_ms, 95)), 2),
            "min_ms": round(float(np.min(latencies_ms)), 2),
            "max_ms": round(float(np.max(latencies_ms)), 2),
            "samples_measured": len(latencies_ms),
        }
    else:
        latency_stats = {"mean_ms": None, "median_ms": None, "p95_ms": None, "samples_measured": 0}

    # 3. Extract confusion matrix counts if available
    tp, fp, fn = 0, 0, 0
    if hasattr(val_results, "confusion_matrix") and val_results.confusion_matrix is not None:
        try:
            cm = val_results.confusion_matrix.matrix
            # cm is of shape (nc + 1, nc + 1) where last row/col is background
            if cm.shape[0] >= 2:
                tp = int(cm[0, 0])
                fp = int(cm[1, 0]) if cm.shape[0] > 1 else 0
                fn = int(cm[0, 1]) if cm.shape[1] > 1 else 0
        except Exception as e:
            logger.warning(f"Could not parse confusion matrix: {e}")

    # 4. Generate visual prediction plot
    sample_plot_path = output_dir / "sample_predictions.png"
    generate_sample_predictions_plot(
        model=model,
        test_images=test_images,
        output_path=sample_plot_path,
        conf_threshold=conf_threshold,
        max_images=6,
    )

    # 5. Sanity check: baseline mAP50 threshold
    passed_validation = map50 >= 0.50
    model_status = "VALIDATED" if passed_validation else "TRAINED_SUBOPTIMAL"

    report = {
        "model_name": "eggvision_detector_yolov8n",
        "weights_path": str(weights_path.resolve()),
        "test_dataset": str(data_yaml.parent.resolve()),
        "test_split_samples": len(test_images),
        "confidence_threshold": conf_threshold,
        "iou_threshold": iou_threshold,
        "metrics": {
            "mAP50": round(map50, 4),
            "mAP50_95": round(map50_95, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
        },
        "confusion_matrix": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
        },
        "latency_benchmark": latency_stats,
        "sample_predictions_plot": str(sample_plot_path.resolve()),
        "validation_passed": passed_validation,
        "model_status": model_status,
        "evaluation_timestamp": datetime.now(UTC).isoformat(),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_file = output_dir / "evaluation_report.json"
    with report_file.open("w", encoding="utf-8") as rf:
        json.dump(report, rf, indent=2)

    logger.info(f"Evaluation report written to {report_file}")

    # 6. Update model_metadata.json if present
    metadata_path = output_dir / "model_metadata.json"
    if metadata_path.exists():
        try:
            with metadata_path.open("r", encoding="utf-8") as mf:
                meta = json.load(mf)
            meta["status"] = model_status
            meta["evaluation_metrics"] = report["metrics"]
            meta["latency_benchmark"] = latency_stats
            meta["evaluated_at"] = report["evaluation_timestamp"]
            with metadata_path.open("w", encoding="utf-8") as mf:
                json.dump(meta, mf, indent=2)
            logger.info(f"Updated status in {metadata_path} to {model_status}")
        except Exception as exc:
            logger.warning(f"Could not update {metadata_path}: {exc}")

    return report


def main():
    parser = argparse.ArgumentParser(description="EggVision AI — Model Evaluation Suite")
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS, help="Path to best.pt weights")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_YAML, help="Path to data.yaml")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=0.50, help="IoU threshold")
    parser.add_argument("--device", type=str, default=None, help="Device ('0', 'cpu', etc.)")
    args = parser.parse_args()

    report = evaluate_detector(
        weights_path=args.weights,
        data_yaml=args.data,
        output_dir=args.output,
        conf_threshold=args.conf,
        iou_threshold=args.iou,
        device=args.device,
    )

    print("\n================== EVALUATION REPORT ==================")
    print(f"Model:           {report['model_name']}")
    print(f"Status:          {report['model_status']} (Validation Passed: {report['validation_passed']})")
    print(f"mAP@0.50:        {report['metrics']['mAP50']:.4f}")
    print(f"mAP@0.50:0.95:   {report['metrics']['mAP50_95']:.4f}")
    print(f"Precision:       {report['metrics']['precision']:.4f}")
    print(f"Recall:          {report['metrics']['recall']:.4f}")
    print(f"F1 Score:        {report['metrics']['f1_score']:.4f}")
    print(f"Latency (Mean):  {report['latency_benchmark']['mean_ms']} ms")
    print(f"Latency (p95):   {report['latency_benchmark']['p95_ms']} ms")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
