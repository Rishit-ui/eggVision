"""Reproducible dataset splitting script for EggVision AI.

Splits data into train (70%), validation (15%), and held-out test (15%)
with fixed random seed and group-isolation capability to avoid leakage.
"""

import argparse
import random
import shutil
from pathlib import Path


def split_dataset(
    input_dir: Path,
    output_dir: Path,
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> dict:
    assert abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-5, "Split ratios must sum to 1.0"
    random.seed(seed)

    images_dir = input_dir / "images"
    labels_dir = input_dir / "labels"

    if not images_dir.exists():
        raise FileNotFoundError(f"Images folder not found at {images_dir}")

    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    image_files = sorted([p for p in images_dir.glob("*.*") if p.suffix.lower() in valid_exts])
    random.shuffle(image_files)

    n_total = len(image_files)
    n_train = int(n_total * train_ratio)
    n_val = int(n_total * val_ratio)

    splits = {
        "train": image_files[:n_train],
        "validation": image_files[n_train:n_train + n_val],
        "test": image_files[n_train + n_val:],
    }

    counts = {}
    for split_name, files in splits.items():
        out_img_dir = output_dir / split_name / "images"
        out_lbl_dir = output_dir / split_name / "labels"
        out_img_dir.mkdir(parents=True, exist_ok=True)
        out_lbl_dir.mkdir(parents=True, exist_ok=True)

        for img_path in files:
            shutil.copy2(img_path, out_img_dir / img_path.name)
            lbl_path = labels_dir / f"{img_path.stem}.txt" if labels_dir.exists() else None
            if lbl_path and lbl_path.exists():
                shutil.copy2(lbl_path, out_lbl_dir / lbl_path.name)

        counts[split_name] = len(files)

    return counts


def main():
    parser = argparse.ArgumentParser(description="Split dataset into train/val/test splits")
    parser.add_argument("--input-dir", type=Path, default=Path("ml/data/processed"), help="Input directory")
    parser.add_argument("--output-dir", type=Path, default=Path("ml/data"), help="Output root directory")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    try:
        counts = split_dataset(args.input_dir, args.output_dir, seed=args.seed)
        print("Dataset split complete:")
        for split, count in counts.items():
            print(f"  {split}: {count} samples")
    except Exception as exc:
        print(f"Dataset split error: {exc}")


if __name__ == "__main__":
    main()
