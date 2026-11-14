#!/usr/bin/env python3
"""split_dataset.py
EggVision ML Foundation — Dataset Splitting Suite.

Partitions dataset into Train (70%), Validation (15%), and Test (15%) splits
with strict reproducible seeding, leakage detection, and YOLO data.yaml generation.

Scientific note: Splitting is performed at the image level because source datasets
do not track physical individual egg specimens across frames.
"""

import argparse
import hashlib
import json
import logging
import random
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("split_dataset")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_IMAGES = REPO_ROOT / "ml" / "data" / "external" / "afshin-dini-egg-detection" / "raw" / "images"
DEFAULT_INPUT_LABELS = REPO_ROOT / "ml" / "data" / "external" / "afshin-dini-egg-detection" / "raw" / "mapped_labels"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "ml" / "data" / "processed" / "egg_detection_yolo"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 digest of a file."""
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def count_labels_in_file(label_path: Path) -> int:
    """Count non-empty lines in a label file."""
    if not label_path.exists():
        return 0
    with label_path.open("r", encoding="utf-8-sig") as f:
        return sum(1 for line in f if line.strip())


def split_dataset(
    images_dir: Path,
    labels_dir: Path,
    output_dir: Path,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> dict[str, Any]:
    """Execute reproducible dataset partitioning with zero-leakage verification."""
    if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 1e-5:
        raise ValueError(f"Ratios must sum to 1.0: {train_ratio} + {val_ratio} + {test_ratio} != 1.0")

    if not images_dir.exists():
        raise FileNotFoundError(f"Input images directory does not exist: {images_dir}")

    valid_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    all_images = sorted([p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in valid_exts])
    total_count = len(all_images)
    if total_count == 0:
        raise RuntimeError(f"No valid image files found in {images_dir}")

    logger.info(f"Loaded {total_count} source images from {images_dir}")

    # Reproducible shuffle
    rng = random.Random(seed)
    shuffled_images = list(all_images)
    rng.shuffle(shuffled_images)

    # Compute partition boundaries
    n_train = int(round(total_count * train_ratio))
    n_val = int(round(total_count * val_ratio))
    # Test gets whatever remains to ensure exact sum
    train_files = shuffled_images[:n_train]
    val_files = shuffled_images[n_train : n_train + n_val]
    test_files = shuffled_images[n_train + n_val :]

    partitions = {
        "train": train_files,
        "val": val_files,
        "test": test_files,
    }

    logger.info(
        f"Partition sizes: train={len(train_files)} ({len(train_files) / total_count:.1%}), "
        f"val={len(val_files)} ({len(val_files) / total_count:.1%}), "
        f"test={len(test_files)} ({len(test_files) / total_count:.1%})"
    )

    # Clean / prepare output directories
    # We use YOLO standard: images/train, images/val, images/test and labels/train, labels/val, labels/test
    partition_hashes: dict[str, set[str]] = {"train": set(), "val": set(), "test": set()}
    partition_stats: dict[str, dict[str, Any]] = {}

    for split_name, files in partitions.items():
        out_img_split = output_dir / "images" / split_name
        out_lbl_split = output_dir / "labels" / split_name
        out_img_split.mkdir(parents=True, exist_ok=True)
        out_lbl_split.mkdir(parents=True, exist_ok=True)

        total_boxes = 0
        file_records = []

        for img_path in files:
            sha = compute_sha256(img_path)
            partition_hashes[split_name].add(sha)

            # Copy image
            dest_img = out_img_split / img_path.name
            shutil.copy2(img_path, dest_img)

            # Copy label
            lbl_name = f"{img_path.stem}.txt"
            src_lbl = labels_dir / lbl_name
            dest_lbl = out_lbl_split / lbl_name
            boxes = 0
            if src_lbl.exists():
                shutil.copy2(src_lbl, dest_lbl)
                boxes = count_labels_in_file(dest_lbl)
            else:
                logger.warning(f"Label missing for {img_path.name} in {labels_dir}")
                # Create empty label file for YOLO
                dest_lbl.touch()

            total_boxes += boxes
            file_records.append(
                {
                    "image": img_path.name,
                    "sha256": sha,
                    "boxes": boxes,
                }
            )

        partition_stats[split_name] = {
            "image_count": len(files),
            "annotation_count": total_boxes,
            "images": [f["image"] for f in file_records],
        }

    # Leakage check: verify no SHA-256 overlap between any splits
    train_val_overlap = partition_hashes["train"].intersection(partition_hashes["val"])
    train_test_overlap = partition_hashes["train"].intersection(partition_hashes["test"])
    val_test_overlap = partition_hashes["val"].intersection(partition_hashes["test"])

    leakage_detected = len(train_val_overlap) > 0 or len(train_test_overlap) > 0 or len(val_test_overlap) > 0

    if leakage_detected:
        msg = f"Data leakage detected! Overlaps: train-val={len(train_val_overlap)}, train-test={len(train_test_overlap)}, val-test={len(val_test_overlap)}"
        logger.error(msg)
        raise RuntimeError(msg)

    logger.info("Zero data leakage verified across train, val, and test splits.")

    # Generate data.yaml for Ultralytics YOLO
    # Note: Use forward slashes for cross-platform compatibility
    data_yaml_path = output_dir / "data.yaml"
    data_yaml_content = f"""# EggVision AI — YOLOv8 / YOLO11 Dataset Configuration
# Generated by ml/scripts/split_dataset.py on {datetime.now(UTC).isoformat()}
# Split methodology: image-level partitioning (seed={seed})
# Scientific disclosure: specimen-level tracking unavailable for this external dataset

path: {output_dir.resolve().as_posix()}
train: images/train
val: images/val
test: images/test

names:
  0: egg

nc: 1
"""
    with data_yaml_path.open("w", encoding="utf-8") as yf:
        yf.write(data_yaml_content)
    logger.info(f"Generated YOLO configuration at {data_yaml_path}")

    # Generate split report
    summary_report = {
        "dataset_name": "egg_detection_yolo",
        "output_directory": str(output_dir.resolve()),
        "split_level": "image-level",
        "scientific_disclosure": (
            "Splitting is strictly image-level because individual physical egg specimens "
            "are not tracked or identified across frames in the afshin-dini/Egg-Detection dataset. "
            "Zero SHA-256 image overlap is mathematically guaranteed across partitions."
        ),
        "random_seed": seed,
        "split_ratios": {"train": train_ratio, "val": val_ratio, "test": test_ratio},
        "total_images": total_count,
        "partitions": partition_stats,
        "leakage_verification": {
            "train_val_overlap": len(train_val_overlap),
            "train_test_overlap": len(train_test_overlap),
            "val_test_overlap": len(val_test_overlap),
            "leakage_detected": leakage_detected,
            "status": "PASSED_ZERO_LEAKAGE",
        },
        "timestamp": datetime.now(UTC).isoformat(),
    }

    summary_path = output_dir / "split_summary.json"
    with summary_path.open("w", encoding="utf-8") as sf:
        json.dump(summary_report, sf, indent=2)
    logger.info(f"Split summary report written to {summary_path}")

    return summary_report


def main():
    parser = argparse.ArgumentParser(description="EggVision AI — Dataset Splitting Suite")
    parser.add_argument("--images-dir", type=Path, default=DEFAULT_INPUT_IMAGES, help="Input images directory")
    parser.add_argument("--labels-dir", type=Path, default=DEFAULT_INPUT_LABELS, help="Input labels directory")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Destination directory for splits")
    parser.add_argument("--train-ratio", type=float, default=0.70, help="Train ratio (default: 0.70)")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="Validation ratio (default: 0.15)")
    parser.add_argument("--test-ratio", type=float, default=0.15, help="Test ratio (default: 0.15)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    report = split_dataset(
        images_dir=args.images_dir,
        labels_dir=args.labels_dir,
        output_dir=args.output_dir,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )
    print("\n================== DATASET SPLIT COMPLETE ==================")
    print(f"Total Images:     {report['total_images']}")
    print(
        f"Train Partition:  {report['partitions']['train']['image_count']} images ({report['partitions']['train']['annotation_count']} boxes)"
    )
    print(
        f"Val Partition:    {report['partitions']['val']['image_count']} images ({report['partitions']['val']['annotation_count']} boxes)"
    )
    print(
        f"Test Partition:   {report['partitions']['test']['image_count']} images ({report['partitions']['test']['annotation_count']} boxes)"
    )
    print(f"Leakage Status:   {report['leakage_verification']['status']}")
    print("============================================================\n")


if __name__ == "__main__":
    main()
