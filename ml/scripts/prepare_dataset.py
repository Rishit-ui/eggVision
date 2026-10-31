"""Image preprocessing and normalization pipeline for training datasets.

Reads raw images, corrects EXIF orientation, applies aspect-preserving resize
to target canonical dimensions, and extracts bounding coordinates.
"""

import argparse
from pathlib import Path
import cv2
import numpy as np


def normalize_image(img_bgr: np.ndarray, target_size: int = 512) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Aspect-preserving resize with letterboxing."""
    h, w = img_bgr.shape[:2]
    scale = min(target_size / h, target_size / w)
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    resized = cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)

    canvas = np.zeros((target_size, target_size, 3), dtype=np.uint8)
    dx = (target_size - new_w) // 2
    dy = (target_size - new_h) // 2
    canvas[dy:dy + new_h, dx:dx + new_w] = resized
    return canvas, scale, (dx, dy)


def prepare_dataset(raw_dir: Path, processed_dir: Path, target_size: int = 512) -> int:
    processed_images = processed_dir / "images"
    processed_images.mkdir(parents=True, exist_ok=True)

    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    count = 0
    for img_path in raw_dir.glob("*.*"):
        if img_path.suffix.lower() not in valid_exts:
            continue
        img = cv2.imread(str(img_path))
        if img is None:
            continue

        canvas, _, _ = normalize_image(img, target_size)
        out_path = processed_images / f"{img_path.stem}.jpg"
        cv2.imwrite(str(out_path), canvas, [cv2.IMWRITE_JPEG_QUALITY, 95])
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Prepare and normalize raw dataset images")
    parser.add_argument("--raw-dir", type=Path, default=Path("ml/data/raw"), help="Raw images directory")
    parser.add_argument("--processed-dir", type=Path, default=Path("ml/data/processed"), help="Output directory")
    parser.add_argument("--target-size", type=int, default=512, help="Canonical dimension")
    args = parser.parse_args()

    processed_count = prepare_dataset(args.raw_dir, args.processed_dir, args.target_size)
    print(f"Successfully processed {processed_count} images into {args.processed_dir}")


if __name__ == "__main__":
    main()
