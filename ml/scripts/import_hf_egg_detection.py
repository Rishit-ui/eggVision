#!/usr/bin/env python3
"""import_hf_egg_detection.py
EggVision ML Foundation — Dataset Importer for Hugging Face afshin-dini/Egg-Detection.

Dataset: afshin-dini/Egg-Detection
License: MIT
Pinned Revision: d425996c959623b3960fca27f53b16f060b0a474
"""

import argparse
import hashlib
import json
import logging
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("import_hf_egg_detection")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "ml" / "data" / "external" / "afshin-dini-egg-detection"

PINNED_REPO_ID = "afshin-dini/Egg-Detection"
PINNED_REVISION = "d425996c959623b3960fca27f53b16f060b0a474"
LICENSE_NAME = "MIT"

CLASS_MAP_ORIGINAL = {
    0: "white-egg",
    1: "brown-egg",
}
TARGET_CLASS_ID = 0
TARGET_CLASS_NAME = "egg"


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 digest of a file in streaming chunks."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_hf_tree(repo_id: str, revision: str) -> list[dict[str, Any]]:
    """Fetch tree listing of files from Hugging Face dataset API."""
    url = f"https://huggingface.co/api/datasets/{repo_id}/tree/{revision}?recursive=true"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "EggVision-Importer/1.0 (+https://github.com/Rishit-ui/eggVision)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(
    repo_id: str,
    revision: str,
    remote_path: str,
    local_path: Path,
    expected_size: int = 0,
    max_retries: int = 3,
) -> bool:
    """Download a single raw file from Hugging Face with retries and validation."""
    if (
        local_path.exists()
        and local_path.stat().st_size > 0
        and (expected_size <= 0 or local_path.stat().st_size == expected_size)
    ):
        logger.debug(f"File already exists and matches expected size: {local_path.name}")
        return True

    url = f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{remote_path}"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = local_path.with_suffix(local_path.suffix + ".tmp")

    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "EggVision-Importer/1.0 (+https://github.com/Rishit-ui/eggVision)"},
            )
            with urllib.request.urlopen(req, timeout=60) as resp, temp_path.open("wb") as out_f:
                total_read = 0
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    total_read += len(chunk)

            if expected_size > 0 and total_read != expected_size:
                raise OSError(f"Size mismatch: got {total_read} bytes, expected {expected_size}")

            temp_path.replace(local_path)
            return True
        except Exception as exc:
            logger.warning(f"Download attempt {attempt}/{max_retries} failed for {remote_path}: {exc}")
            if temp_path.exists():
                temp_path.unlink()
            if attempt < max_retries:
                time.sleep(2 * attempt)
            else:
                logger.error(f"Permanent download failure for {remote_path}")
                return False
    return False


def validate_and_map_yolo_labels(
    raw_label_path: Path,
    mapped_label_path: Path,
) -> tuple[bool, list[dict[str, Any]], list[str]]:
    """Validate YOLO bounding boxes and map classes to generic 'egg' (0)."""
    boxes = []
    errors = []
    mapped_lines = []

    if not raw_label_path.exists():
        return False, [], [f"Label file missing: {raw_label_path.name}"]

    with raw_label_path.open("r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    for line_idx, line in enumerate(lines, 1):
        line_clean = line.strip()
        if not line_clean:
            continue
        parts = line_clean.split()
        if len(parts) != 5:
            errors.append(
                f"{raw_label_path.name}:{line_idx} - Invalid YOLO format (expected 5 tokens, got {len(parts)})"
            )
            continue

        try:
            cls_id = int(parts[0])
            xc = float(parts[1])
            yc = float(parts[2])
            w = float(parts[3])
            h = float(parts[4])
        except ValueError as e:
            errors.append(f"{raw_label_path.name}:{line_idx} - Non-numeric coordinate: {e}")
            continue

        # Check bounds
        if not (0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0):
            errors.append(f"{raw_label_path.name}:{line_idx} - Center ({xc}, {yc}) out of [0, 1]")
        if not (0.0 < w <= 1.0 and 0.0 < h <= 1.0):
            errors.append(f"{raw_label_path.name}:{line_idx} - Dimension w={w}, h={h} out of (0, 1]")

        orig_class_name = CLASS_MAP_ORIGINAL.get(cls_id, f"unknown_{cls_id}")
        boxes.append(
            {
                "line": line_idx,
                "original_class_id": cls_id,
                "original_class_name": orig_class_name,
                "mapped_class_id": TARGET_CLASS_ID,
                "mapped_class_name": TARGET_CLASS_NAME,
                "xc": xc,
                "yc": yc,
                "w": w,
                "h": h,
            }
        )
        # Write mapped line (target class 0)
        mapped_lines.append(f"{TARGET_CLASS_ID} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")

    mapped_label_path.parent.mkdir(parents=True, exist_ok=True)
    with mapped_label_path.open("w", encoding="utf-8") as mf:
        mf.writelines(mapped_lines)

    is_valid = len(errors) == 0
    return is_valid, boxes, errors


def run_import(
    repo_id: str = PINNED_REPO_ID,
    revision: str = PINNED_REVISION,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    force: bool = False,
) -> dict[str, Any]:
    """Execute complete dataset importation and verification."""
    start_time = datetime.now(UTC)
    logger.info(f"Starting import of {repo_id} at revision {revision}")
    logger.info(f"Destination directory: {output_dir}")

    raw_images_dir = output_dir / "raw" / "images"
    raw_labels_dir = output_dir / "raw" / "labels"
    mapped_labels_dir = output_dir / "raw" / "mapped_labels"

    raw_images_dir.mkdir(parents=True, exist_ok=True)
    raw_labels_dir.mkdir(parents=True, exist_ok=True)
    mapped_labels_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fetch tree from Hugging Face
    tree = fetch_hf_tree(repo_id, revision)
    logger.info(f"Retrieved remote tree with {len(tree)} entries")

    # Filter image and label files
    image_entries = [
        item
        for item in tree
        if item.get("type") == "file"
        and item.get("path", "").startswith("data/images/")
        and item.get("path", "").lower().endswith((".jpg", ".jpeg", ".png"))
    ]
    label_entries = {
        Path(item.get("path")).name: item
        for item in tree
        if item.get("type") == "file"
        and item.get("path", "").startswith("data/labels/")
        and item.get("path", "").endswith(".txt")
    }

    logger.info(f"Found {len(image_entries)} remote image files and {len(label_entries)} remote label files")

    # Download images and labels
    downloaded_images = 0
    failed_downloads = []
    image_hashes: dict[str, str] = {}
    class_distribution_original = {"white-egg": 0, "brown-egg": 0}
    class_distribution_mapped = {"egg": 0}
    total_annotations = 0
    validation_errors = []
    per_image_metadata: dict[str, Any] = {}

    for idx, img_item in enumerate(image_entries, 1):
        remote_img_path = img_item["path"]
        img_name = Path(remote_img_path).name
        label_name = f"{Path(img_name).stem}.txt"
        local_img_path = raw_images_dir / img_name
        local_label_path = raw_labels_dir / label_name
        mapped_label_path = mapped_labels_dir / label_name

        expected_size = img_item.get("size", 0)
        logger.info(
            f"[{idx}/{len(image_entries)}] Downloading image: {img_name} ({expected_size / 1024 / 1024:.2f} MB)"
        )

        img_ok = download_file(
            repo_id=repo_id,
            revision=revision,
            remote_path=remote_img_path,
            local_path=local_img_path,
            expected_size=expected_size,
        )
        if not img_ok:
            failed_downloads.append(remote_img_path)
            continue

        downloaded_images += 1
        sha256 = compute_sha256(local_img_path)
        image_hashes[img_name] = sha256

        # Download corresponding label file
        if label_name in label_entries:
            remote_label_path = label_entries[label_name]["path"]
            label_size = label_entries[label_name].get("size", 0)
            lbl_ok = download_file(
                repo_id=repo_id,
                revision=revision,
                remote_path=remote_label_path,
                local_path=local_label_path,
                expected_size=label_size,
            )
            if not lbl_ok:
                failed_downloads.append(remote_label_path)
                continue
        else:
            validation_errors.append(f"No remote label entry for image: {img_name}")
            continue

        # Validate bounding boxes and map labels
        valid, boxes, errs = validate_and_map_yolo_labels(local_label_path, mapped_label_path)
        if not valid:
            validation_errors.extend(errs)

        img_white = sum(1 for b in boxes if b["original_class_id"] == 0)
        img_brown = sum(1 for b in boxes if b["original_class_id"] == 1)
        class_distribution_original["white-egg"] += img_white
        class_distribution_original["brown-egg"] += img_brown
        class_distribution_mapped["egg"] += len(boxes)
        total_annotations += len(boxes)

        per_image_metadata[img_name] = {
            "image_id": Path(img_name).stem,
            "filename": img_name,
            "remote_path": remote_img_path,
            "file_size_bytes": local_img_path.stat().st_size,
            "sha256": sha256,
            "annotation_count": len(boxes),
            "original_counts": {"white-egg": img_white, "brown-egg": img_brown},
            "mapped_counts": {"egg": len(boxes)},
            "boxes": boxes,
        }

    status = (
        "PASSED"
        if (len(failed_downloads) == 0 and len(validation_errors) == 0 and downloaded_images == 51)
        else "FAILED"
    )

    report = {
        "dataset_name": "afshin-dini/Egg-Detection",
        "repository_url": f"https://huggingface.co/datasets/{repo_id}",
        "revision_pinned": revision,
        "commit_hash": revision,
        "license": LICENSE_NAME,
        "total_images_downloaded": downloaded_images,
        "total_images_expected": len(image_entries),
        "total_annotations": total_annotations,
        "class_distribution_original": class_distribution_original,
        "class_distribution_mapped": class_distribution_mapped,
        "validation_status": status,
        "validation_errors": validation_errors,
        "failed_downloads": failed_downloads,
        "import_timestamp": start_time.isoformat(),
        "completion_timestamp": datetime.now(UTC).isoformat(),
        "image_hashes": image_hashes,
        "per_image_metadata": per_image_metadata,
    }

    report_path = output_dir / "import_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Import report written to {report_path}")
    logger.info(f"Import status: {status} ({downloaded_images} images, {total_annotations} annotations)")
    return report


def main():
    parser = argparse.ArgumentParser(description="Import Hugging Face afshin-dini/Egg-Detection dataset")
    parser.add_argument("--repo-id", default=PINNED_REPO_ID, help="Hugging Face dataset repository ID")
    parser.add_argument("--revision", default=PINNED_REVISION, help="Pinned Git commit SHA")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Destination directory")
    parser.add_argument("--force", action="store_true", help="Force redownload of existing files")
    args = parser.parse_args()

    report = run_import(
        repo_id=args.repo_id,
        revision=args.revision,
        output_dir=args.output_dir,
        force=args.force,
    )
    if report["validation_status"] != "PASSED":
        logger.error(f"Import finished with issues: {report['validation_errors']}")
        sys.exit(1)
    logger.info("Import completed successfully.")


if __name__ == "__main__":
    main()
