#!/usr/bin/env python3
"""validate_dataset.py
EggVision ML Foundation — Dataset Validation and Integrity Suite.

Performs comprehensive validation:
1. Image decodability and integrity (OpenCV / PIL).
2. Image dimension validation (width > 0, height > 0).
3. YOLO bounding box validation:
   - 5 elements per row
   - class_id in range [0, num_classes - 1]
   - normalized coordinates xc, yc in [0, 1]
   - normalized dimensions w, h in (0, 1]
   - box boundaries xc - w/2 >= 0, xc + w/2 <= 1 (with small numerical tolerance)
4. Duplicate image detection (SHA-256 exact match and 64-bit difference hash).
5. Missing labels for images and orphaned labels without images.
6. Class distribution and imbalance analysis.
7. Outputs structured report to ml/data/reports/dataset_validation_report.json.
"""

import argparse
import hashlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("validate_dataset")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = REPO_ROOT / "ml" / "data" / "reports" / "dataset_validation_report.json"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 digest of a file."""
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_dhash(img: np.ndarray, hash_size: int = 8) -> str:
    """Compute 64-bit difference hash (dHash) for near-duplicate detection."""
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        resized = cv2.resize(gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
        # Compute horizontal differences
        diff = resized[:, 1:] > resized[:, :-1]
        # Convert bool array to hex string
        return hex(int("".join(["1" if b else "0" for b in diff.flatten()]), 2))[2:].zfill(hash_size * hash_size // 4)
    except Exception:
        return ""


def validate_yolo_bbox(
    line: str,
    line_no: int,
    label_path: Path,
    num_classes: int,
    tolerance: float = 0.05,
) -> tuple[bool, int | None, list[float], str]:
    """Validate a single YOLO format bounding box entry.

    Format: class_id xc yc w h (all normalized [0.0, 1.0])
    """
    parts = line.strip().split()
    if len(parts) != 5:
        return False, None, [], f"Line {line_no}: Expected 5 elements, found {len(parts)}"

    try:
        class_id = int(parts[0])
        xc, yc, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
    except ValueError as e:
        return False, None, [], f"Line {line_no}: Malformed numerical values ({e})"

    if class_id < 0 or class_id >= num_classes:
        return (
            False,
            class_id,
            [xc, yc, w, h],
            f"Line {line_no}: Class ID {class_id} outside valid range [0, {num_classes - 1}]",
        )

    if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0):
        return False, class_id, [xc, yc, w, h], f"Line {line_no}: Center ({xc:.4f}, {yc:.4f}) outside [0.0, 1.0]"

    if not (0.0 < w <= 1.0 and 0.0 < h <= 1.0):
        return False, class_id, [xc, yc, w, h], f"Line {line_no}: Size w={w:.4f}, h={h:.4f} outside (0.0, 1.0]"

    # Boundary check with tolerance for edge-bleed
    x_min = xc - w / 2.0
    x_max = xc + w / 2.0
    y_min = yc - h / 2.0
    y_max = yc + h / 2.0

    if x_min < -tolerance or x_max > 1.0 + tolerance or y_min < -tolerance or y_max > 1.0 + tolerance:
        return (
            False,
            class_id,
            [xc, yc, w, h],
            (
                f"Line {line_no}: Bounding box exceeds frame boundaries "
                f"([x1={x_min:.4f}, y1={y_min:.4f}, x2={x_max:.4f}, y2={y_max:.4f}])"
            ),
        )

    return True, class_id, [xc, yc, w, h], ""


def validate_dataset_directory(
    images_dir: Path,
    labels_dir: Path | None = None,
    num_classes: int = 1,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Execute complete validation suite on images and labels directories."""
    valid_image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

    stats: dict[str, Any] = {
        "images_directory": str(images_dir),
        "labels_directory": str(labels_dir) if labels_dir else None,
        "num_classes": num_classes,
        "total_images": 0,
        "valid_images": 0,
        "corrupt_images": 0,
        "missing_labels": 0,
        "orphaned_labels": 0,
        "duplicate_images": 0,
        "near_duplicate_images": 0,
        "bounding_box_errors": 0,
        "total_bounding_boxes": 0,
        "class_distribution": {},
        "summary_status": "PENDING",
        "validation_errors": [],
        "image_details": {},
    }

    if not images_dir.exists():
        stats["summary_status"] = "FAILED"
        stats["validation_errors"].append(f"Images directory not found: {images_dir}")
        return stats

    image_files = [p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in valid_image_exts]
    stats["total_images"] = len(image_files)

    seen_sha: dict[str, Path] = {}
    seen_dhash: dict[str, Path] = {}
    image_stems: set[str] = set()

    for img_path in sorted(image_files):
        stem = img_path.stem
        image_stems.add(stem)

        # 1. SHA-256 exact duplicate check
        sha = compute_sha256(img_path)
        if sha in seen_sha:
            stats["duplicate_images"] += 1
            stats["validation_errors"].append(f"Duplicate image: {img_path.name} is identical to {seen_sha[sha].name}")
            continue
        seen_sha[sha] = img_path

        # 2. Decodability and dimensions check
        img = cv2.imread(str(img_path))
        if img is None or img.size == 0:
            stats["corrupt_images"] += 1
            stats["validation_errors"].append(f"Corrupt image file (cannot decode): {img_path.name}")
            continue

        h, w = img.shape[:2]
        if w <= 0 or h <= 0:
            stats["corrupt_images"] += 1
            stats["validation_errors"].append(f"Invalid dimensions {w}x{h}: {img_path.name}")
            continue

        # 3. Near-duplicate check via dHash
        dh = compute_dhash(img)
        if dh and dh in seen_dhash:
            stats["near_duplicate_images"] += 1
            # Note: Near duplicates in multi-angle datasets are logged as warnings, not fatal errors
            logger.debug(f"Perceptual near-duplicate: {img_path.name} matches {seen_dhash[dh].name}")
        elif dh:
            seen_dhash[dh] = img_path

        stats["valid_images"] += 1

        img_detail = {
            "filename": img_path.name,
            "width": w,
            "height": h,
            "channels": img.shape[2] if len(img.shape) == 3 else 1,
            "sha256": sha,
            "dhash": dh,
            "boxes_count": 0,
            "labels": [],
        }

        # 4. Check labels
        if labels_dir and labels_dir.exists():
            label_file = labels_dir / f"{stem}.txt"
            if not label_file.exists():
                stats["missing_labels"] += 1
                stats["validation_errors"].append(f"Missing label file for image: {img_path.name}")
            else:
                with label_file.open("r", encoding="utf-8-sig") as lf:
                    lines = lf.readlines()

                img_boxes = 0
                for line_idx, line in enumerate(lines, 1):
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                    is_valid, cls_id, bbox, err_msg = validate_yolo_bbox(
                        line_clean, line_idx, label_file, num_classes, tolerance
                    )
                    if not is_valid:
                        stats["bounding_box_errors"] += 1
                        stats["validation_errors"].append(f"{label_file.name}:{err_msg}")
                    else:
                        img_boxes += 1
                        stats["total_bounding_boxes"] += 1
                        stats["class_distribution"][cls_id] = stats["class_distribution"].get(cls_id, 0) + 1
                        img_detail["labels"].append({"class_id": cls_id, "bbox": bbox})

                img_detail["boxes_count"] = img_boxes

        stats["image_details"][img_path.name] = img_detail

    # 5. Check for orphaned label files (labels with no corresponding image)
    if labels_dir and labels_dir.exists():
        for label_path in labels_dir.glob("*.txt"):
            if label_path.stem not in image_stems:
                stats["orphaned_labels"] += 1
                stats["validation_errors"].append(f"Orphaned label file (no matching image): {label_path.name}")

    # Determine summary status
    if (
        stats["corrupt_images"] == 0
        and stats["missing_labels"] == 0
        and stats["bounding_box_errors"] == 0
        and stats["duplicate_images"] == 0
        and stats["orphaned_labels"] == 0
        and stats["valid_images"] > 0
    ):
        stats["summary_status"] = "PASSED"
    else:
        stats["summary_status"] = "FAILED"

    stats["validation_timestamp"] = datetime.now(UTC).isoformat()
    return stats


def main():
    parser = argparse.ArgumentParser(description="EggVision AI — Dataset Validation Suite")
    parser.add_argument("--images-dir", type=Path, default=None, help="Directory containing images")
    parser.add_argument("--labels-dir", type=Path, default=None, help="Directory containing YOLO labels")
    parser.add_argument("--data-root", type=Path, default=None, help="Dataset root containing images/ and labels/")
    parser.add_argument("--num-classes", type=int, default=1, help="Expected number of classes")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_PATH, help="Path to write JSON validation report")
    parser.add_argument("--tolerance", type=float, default=0.05, help="Boundary tolerance for edge bounding boxes")
    args = parser.parse_args()

    # Determine directories
    if args.data_root:
        images_dir = (
            args.data_root / "images" if (args.data_root / "images").exists() else args.data_root / "raw" / "images"
        )
        labels_dir = (
            args.data_root / "labels"
            if (args.data_root / "labels").exists()
            else args.data_root / "raw" / "mapped_labels"
        )
        if not labels_dir.exists():
            labels_dir = args.data_root / "raw" / "labels"
    else:
        # Default auto-detect
        ext_dir = REPO_ROOT / "ml" / "data" / "external" / "afshin-dini-egg-detection"
        if (ext_dir / "raw" / "images").exists():
            images_dir = ext_dir / "raw" / "images"
            labels_dir = (
                ext_dir / "raw" / "mapped_labels"
                if (ext_dir / "raw" / "mapped_labels").exists()
                else ext_dir / "raw" / "labels"
            )
        else:
            images_dir = REPO_ROOT / "ml" / "data" / "raw"
            labels_dir = None

    if args.images_dir:
        images_dir = args.images_dir
    if args.labels_dir:
        labels_dir = args.labels_dir

    logger.info("Validating dataset:")
    logger.info(f"  Images: {images_dir}")
    logger.info(f"  Labels: {labels_dir}")
    logger.info(f"  Num Classes: {args.num_classes}")

    results = validate_dataset_directory(
        images_dir=images_dir,
        labels_dir=labels_dir,
        num_classes=args.num_classes,
        tolerance=args.tolerance,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Validation report saved to {args.output}")

    print("\n================== EGGVISION DATASET VALIDATION ==================")
    print(f"Summary Status:        {results['summary_status']}")
    print(f"Total Images:          {results['total_images']}")
    print(f"Valid Images:          {results['valid_images']}")
    print(f"Corrupt Images:        {results['corrupt_images']}")
    print(f"Duplicate Images:      {results['duplicate_images']}")
    print(f"Near-Duplicate Images: {results['near_duplicate_images']}")
    print(f"Missing Labels:        {results['missing_labels']}")
    print(f"Orphaned Labels:       {results['orphaned_labels']}")
    print(f"Total Bounding Boxes:  {results['total_bounding_boxes']}")
    print(f"Bounding Box Errors:   {results['bounding_box_errors']}")
    print(f"Class Distribution:    {results['class_distribution']}")
    print("==================================================================\n")

    if results["summary_status"] != "PASSED":
        logger.warning(f"Validation reported {len(results['validation_errors'])} errors:")
        for err in results["validation_errors"][:10]:
            logger.warning(f"  * {err}")
        if len(results["validation_errors"]) > 10:
            logger.warning(f"  ... and {len(results['validation_errors']) - 10} more.")
        sys.exit(1)
    else:
        logger.info("Dataset validation passed all integrity checks.")


if __name__ == "__main__":
    main()
