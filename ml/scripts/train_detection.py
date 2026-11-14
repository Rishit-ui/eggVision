#!/usr/bin/env python3
"""train_detection.py
EggVision ML Foundation — Model A: Egg Detection Training Suite.

Trains Ultralytics YOLOv8n detector on the verified egg detection dataset.
Supports GPU acceleration with graceful CPU fallback on OOM, reproducible seeding,
artifact registry export, and comprehensive training metadata generation.
"""

import argparse
import hashlib
import json
import logging
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import torch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("train_detection")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_YAML = REPO_ROOT / "ml" / "data" / "processed" / "egg_detection_yolo" / "data.yaml"
DEFAULT_ARTIFACTS_DIR = REPO_ROOT / "ml" / "artifacts" / "detection"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 digest of a file."""
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def count_split_images(data_dir: Path) -> dict[str, int]:
    """Count number of images in each split."""
    counts = {}
    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    for split in ["train", "val", "test"]:
        split_dir = data_dir / "images" / split
        if split_dir.exists():
            counts[split] = len([p for p in split_dir.iterdir() if p.suffix.lower() in valid_exts])
        else:
            counts[split] = 0
    return counts


def train_egg_detector(
    data_yaml: Path = DEFAULT_DATA_YAML,
    base_model: str = "yolov8n.pt",
    epochs: int = 30,
    batch_size: int = 8,
    img_size: int = 640,
    output_dir: Path = DEFAULT_ARTIFACTS_DIR,
    seed: int = 42,
    patience: int = 10,
    workers: int = 2,
    device: str | None = None,
) -> dict[str, Any]:
    """Train YOLO egg detection model with integrity verification and artifact generation."""
    from ultralytics import YOLO

    if not data_yaml.exists():
        raise FileNotFoundError(f"Dataset configuration '{data_yaml}' not found. Run import and split scripts first.")

    # Determine hardware device
    if device is None:
        if torch.cuda.is_available():
            device = "0"
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"CUDA GPU detected: {gpu_name} (Device: {device})")
        else:
            device = "cpu"
            gpu_name = "CPU"
            logger.info("No CUDA GPU detected; using CPU.")
    else:
        gpu_name = device

    output_dir.mkdir(parents=True, exist_ok=True)
    weights_dir = output_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    runs_dir = output_dir / "runs"

    start_time = time.time()
    start_iso = datetime.now(UTC).isoformat()

    logger.info("Initializing Ultralytics YOLO model...")
    logger.info(f"Base model: {base_model}, epochs: {epochs}, batch: {batch_size}, img_size: {img_size}")

    model = YOLO(base_model)

    train_results = None

    try:
        logger.info(f"Starting training on device={device}...")
        train_results = model.train(
            data=str(data_yaml.resolve().as_posix()),
            epochs=epochs,
            batch=batch_size,
            imgsz=img_size,
            device=device,
            seed=seed,
            patience=patience,
            workers=workers,
            project=str(runs_dir.resolve().as_posix()),
            name="train_run",
            exist_ok=True,
            verbose=True,
            val=True,
            save=True,
        )
    except torch.cuda.OutOfMemoryError as oom_err:
        logger.warning(f"CUDA OutOfMemory on device {device}: {oom_err}. Retrying with batch_size=4 or CPU...")
        torch.cuda.empty_cache()
        # Fallback to CPU or smaller batch
        fallback_device = "cpu"
        logger.info(f"Retrying training on device={fallback_device}...")
        train_results = model.train(
            data=str(data_yaml.resolve().as_posix()),
            epochs=epochs,
            batch=4,
            imgsz=img_size,
            device=fallback_device,
            seed=seed,
            patience=patience,
            workers=0,
            project=str(runs_dir.resolve().as_posix()),
            name="train_run",
            exist_ok=True,
            verbose=True,
            val=True,
            save=True,
        )
        gpu_name = f"{gpu_name} (Fell back to CPU due to OOM)"

    duration_seconds = time.time() - start_time
    logger.info(f"Training completed in {duration_seconds:.2f} seconds.")

    # Locate generated best.pt and last.pt
    run_save_dir = runs_dir / "train_run"
    run_weights_dir = run_save_dir / "weights"
    best_pt_src = run_weights_dir / "best.pt"
    last_pt_src = run_weights_dir / "last.pt"

    best_pt_dst = weights_dir / "best.pt"
    last_pt_dst = weights_dir / "last.pt"

    if best_pt_src.exists():
        shutil.copy2(best_pt_src, best_pt_dst)
        logger.info(f"Copied best model weights to {best_pt_dst}")
    else:
        raise RuntimeError(f"Expected best model weights not found at {best_pt_src}")

    if last_pt_src.exists():
        shutil.copy2(last_pt_src, last_pt_dst)
        logger.info(f"Copied last model weights to {last_pt_dst}")

    # Copy args.yaml and results.csv if present
    if (run_save_dir / "args.yaml").exists():
        shutil.copy2(run_save_dir / "args.yaml", output_dir / "args.yaml")
    if (run_save_dir / "results.csv").exists():
        shutil.copy2(run_save_dir / "results.csv", output_dir / "results.csv")

    best_sha256 = compute_sha256(best_pt_dst)
    sample_counts = count_split_images(data_yaml.parent)

    # Extract training metrics if available
    train_metrics = {}
    if hasattr(train_results, "results_dict") and train_results.results_dict:
        train_metrics = {k: float(v) for k, v in train_results.results_dict.items() if isinstance(v, (int, float))}

    # Prepare model metadata
    metadata = {
        "model_name": "eggvision_detector_yolov8n",
        "model_architecture": base_model.replace(".pt", ""),
        "task": "detection",
        "classes": {0: "egg"},
        "training_dataset": "afshin-dini/Egg-Detection",
        "training_samples": sample_counts.get("train", 0),
        "validation_samples": sample_counts.get("val", 0),
        "test_samples": sample_counts.get("test", 0),
        "input_resolution": [img_size, img_size],
        "epochs_requested": epochs,
        "batch_size": batch_size,
        "seed": seed,
        "hardware_device": gpu_name,
        "training_duration_seconds": round(duration_seconds, 2),
        "weights_path": str(best_pt_dst.resolve()),
        "weights_sha256": best_sha256,
        "weights_size_bytes": best_pt_dst.stat().st_size,
        "training_metrics": train_metrics,
        "status": "TRAINED_UNVALIDATED",
        "created_at": start_iso,
        "completed_at": datetime.now(UTC).isoformat(),
    }

    meta_file = output_dir / "model_metadata.json"
    with meta_file.open("w", encoding="utf-8") as mf:
        json.dump(metadata, mf, indent=2)

    logger.info(f"Model metadata successfully written to {meta_file}")
    return metadata


def main():
    parser = argparse.ArgumentParser(description="EggVision AI — Egg Detection Model Training")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_YAML, help="Path to data.yaml")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="Base model architecture")
    parser.add_argument("--epochs", type=int, default=30, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    parser.add_argument("--img-size", type=int, default=640, help="Input image dimension")
    parser.add_argument("--output", type=Path, default=DEFAULT_ARTIFACTS_DIR, help="Output directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--device", type=str, default=None, help="Device ('0', 'cpu', etc.)")
    args = parser.parse_args()

    meta = train_egg_detector(
        data_yaml=args.data,
        base_model=args.model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        img_size=args.img_size,
        output_dir=args.output,
        seed=args.seed,
        device=args.device,
    )
    print("\n================== TRAINING COMPLETE ==================")
    print(f"Model:           {meta['model_name']}")
    print(f"Weights SHA-256: {meta['weights_sha256']}")
    print(f"Duration:        {meta['training_duration_seconds']}s")
    print(f"Status:          {meta['status']}")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
