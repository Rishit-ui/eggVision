"""Dataset validation script for EggVision AI.

Checks for:
1. Missing annotations or corrupt images.
2. Out-of-bounds bounding boxes or inverted coordinates.
3. Unsupported class IDs.
4. Duplicate image detection via perceptual hashing / SHA-256.
5. Class imbalance reporting.
"""

import argparse
import hashlib
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import cv2
import numpy as np


def compute_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_yolo_bbox(line: str, line_no: int, filepath: Path, num_classes: int) -> tuple[bool, str]:
    parts = line.strip().split()
    if len(parts) != 5:
        return False, f"Line {line_no}: Expected 5 elements, found {len(parts)}"
    try:
        class_id = int(parts[0])
        xc, yc, w, h = map(float, parts[1:])
    except ValueError:
        return False, f"Line {line_no}: Malformed numerical values"

    if class_id < 0 or class_id >= num_classes:
        return False, f"Line {line_no}: Class ID {class_id} outside range [0, {num_classes - 1}]"
    if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0):
        return False, f"Line {line_no}: Bounding box coordinates outside [0.0, 1.0]"
    return True, ""


def validate_dataset(data_dir: Path, num_classes: int = 1) -> dict:
    images_dir = data_dir / "images"
    labels_dir = data_dir / "labels"

    stats = {
        "valid_images": 0,
        "corrupt_images": 0,
        "missing_labels": 0,
        "duplicate_images": 0,
        "class_counts": {},
        "errors": [],
    }

    if not images_dir.exists():
        stats["errors"].append(f"Images directory not found: {images_dir}")
        return stats

    seen_hashes = {}
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}

    for img_path in images_dir.glob("*.*"):
        if img_path.suffix.lower() not in valid_exts:
            continue

        # Check duplicate
        sha = compute_sha256(img_path)
        if sha in seen_hashes:
            stats["duplicate_images"] += 1
            stats["errors"].append(f"Duplicate image: {img_path.name} matches {seen_hashes[sha].name}")
            continue
        seen_hashes[sha] = img_path

        # Check image decodability
        img = cv2.imread(str(img_path))
        if img is None or img.size == 0:
            stats["corrupt_images"] += 1
            stats["errors"].append(f"Corrupt image file: {img_path.name}")
            continue

        stats["valid_images"] += 1

        # Check corresponding label
        label_path = labels_dir / f"{img_path.stem}.txt" if labels_dir.exists() else None
        if label_path and label_path.exists():
            with open(label_path, "r", encoding="utf-8") as lf:
                for line_idx, line in enumerate(lf, 1):
                    line_clean = line.strip()
                    if not line_clean:
                        continue
                    valid, err = validate_yolo_bbox(line_clean, line_idx, label_path, num_classes)
                    if not valid:
                        stats["errors"].append(f"{label_path.name}: {err}")
                    else:
                        cls_id = int(line_clean.split()[0])
                        stats["class_counts"][cls_id] = stats["class_counts"].get(cls_id, 0) + 1
        elif labels_dir.exists():
            stats["missing_labels"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Validate dataset integrity for EggVision AI")
    parser.add_argument("--data-dir", type=Path, default=Path("ml/data"), help="Path to dataset root")
    parser.add_argument("--num-classes", type=int, default=1, help="Expected number of classes")
    args = parser.parse_args()

    results = validate_dataset(args.data_dir, args.num_classes)
    print("--- EggVision Dataset Validation Results ---")
    print(f"Valid images: {results['valid_images']}")
    print(f"Corrupt images: {results['corrupt_images']}")
    print(f"Duplicate images: {results['duplicate_images']}")
    print(f"Class distribution: {results['class_counts']}")
    if results["errors"]:
        print(f"Total Errors Found: {len(results['errors'])}")
        for err in results["errors"][:10]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
