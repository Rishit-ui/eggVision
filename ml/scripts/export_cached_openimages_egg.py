#!/usr/bin/env python3
"""Export cached Open Images Egg (Food) samples without starting FiftyOne/MongoDB.

Place this file at ml/scripts/export_cached_openimages_egg.py and run it from the
repository root with the project's FiftyOne venv Python 3.11 executable.

The script streams the large detection and image metadata CSVs; it does not load
either file fully into memory and does not download anything.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

EGG_MID = "/m/033cnk"
EGG_DISPLAY_NAME = "Egg (Food)"


def repo_paths(script_path: Path) -> dict[str, Path]:
    # Expected location: <repo>/ml/scripts/export_cached_openimages_egg.py
    root = script_path.resolve().parents[2]
    train = root / "ml" / "data" / "fiftyone_cache" / "open-images-v7" / "train"
    return {
        "root": root,
        "train": train,
        "images": train / "data",
        "detections": train / "labels" / "detections.csv",
        "image_info": train / "metadata" / "image_ids.csv",
        "raw": root / "ml" / "data" / "raw",
        "inspection": root / "ml" / "data" / "inspection_report.csv",
        "contact_sheet": root / "ml" / "data" / "egg_inspection_contact_sheet.jpg",
        "filtered_annotations": root / "ml" / "data" / "openimages_egg_detection_boxes.csv",
    }


def norm_id(value: str) -> str:
    return value.strip().lower()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def md5_base64_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return base64.b64encode(digest.digest()).decode("ascii")


def find_cached_images(image_dir: Path) -> dict[str, Path]:
    if not image_dir.is_dir():
        raise FileNotFoundError(f"Cached image directory not found: {image_dir}")
    images: dict[str, Path] = {}
    for path in sorted(image_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg"}:
            images[norm_id(path.stem)] = path
    if not images:
        raise RuntimeError(f"No cached JPEGs found under {image_dir}")
    return images


def read_egg_boxes(csv_path: Path, cached_ids: set[str]) -> tuple[dict[str, list[dict[str, Any]]], int, int]:
    """Stream the large annotation CSV and retain only boxes for cached Egg MID images."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Detection annotation CSV not found: {csv_path}")

    boxes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    matching_rows = 0
    invalid_rows = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"ImageID", "LabelName", "XMin", "XMax", "YMin", "YMax"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Detection CSV is missing required columns: {sorted(missing)}")

        for row in reader:
            image_id = norm_id(row.get("ImageID", ""))
            if image_id not in cached_ids or row.get("LabelName", "").strip() != EGG_MID:
                continue

            matching_rows += 1
            try:
                xmin = float(row["XMin"])
                xmax = float(row["XMax"])
                ymin = float(row["YMin"])
                ymax = float(row["YMax"])
                values = (xmin, xmax, ymin, ymax)
                if not all(0.0 <= value <= 1.0 for value in values):
                    raise ValueError("box coordinate outside [0, 1]")
                if xmin >= xmax or ymin >= ymax:
                    raise ValueError("box has non-positive width or height")
            except (TypeError, ValueError, KeyError):
                invalid_rows += 1
                continue

            boxes[image_id].append({
                "label_mid": EGG_MID,
                "label_name": EGG_DISPLAY_NAME,
                "source": row.get("Source", ""),
                "confidence": row.get("Confidence", ""),
                "xmin": xmin,
                "xmax": xmax,
                "ymin": ymin,
                "ymax": ymax,
                "is_occluded": row.get("IsOccluded", ""),
                "is_truncated": row.get("IsTruncated", ""),
                "is_group_of": row.get("IsGroupOf", ""),
                "is_depiction": row.get("IsDepiction", ""),
                "is_inside": row.get("IsInside", ""),
            })

    return dict(boxes), matching_rows, invalid_rows


def read_image_metadata(csv_path: Path, wanted_ids: set[str]) -> dict[str, dict[str, str]]:
    """Stream Open Images image_ids.csv and retain provenance for selected IDs."""
    if not csv_path.is_file():
        raise FileNotFoundError(f"Image metadata CSV not found: {csv_path}")

    metadata: dict[str, dict[str, str]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"ImageID", "Subset", "OriginalURL", "OriginalLandingURL", "License", "Author", "OriginalMD5"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Image metadata CSV is missing required columns: {sorted(missing)}")

        for row in reader:
            image_id = norm_id(row.get("ImageID", ""))
            if image_id in wanted_ids:
                metadata[image_id] = {key: (value or "") for key, value in row.items() if key}
                if len(metadata) == len(wanted_ids):
                    break
    return metadata


def load_existing_review(path: Path) -> dict[str, dict[str, str]]:
    existing: dict[str, dict[str, str]] = {}
    if not path.is_file():
        return existing
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            image_id = norm_id(row.get("image_id", ""))
            if image_id:
                existing[image_id] = row
    return existing


def save_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def make_contact_sheet(entries: list[dict[str, Any]], output: Path, columns: int = 2) -> None:
    if not entries:
        raise RuntimeError("No eligible images available for contact sheet")

    tile_w, image_h, label_h, pad = 420, 300, 48, 14
    rows = (len(entries) + columns - 1) // columns
    sheet = Image.new("RGB", (pad + columns * (tile_w + pad), pad + rows * (image_h + label_h + pad)), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 17)
    except OSError:
        font = ImageFont.load_default()

    for index, entry in enumerate(entries):
        col, row = index % columns, index // columns
        x = pad + col * (tile_w + pad)
        y = pad + row * (image_h + label_h + pad)
        with Image.open(entry["source_path"]) as raw:
            image = ImageOps.exif_transpose(raw).convert("RGB")
            image.thumbnail((tile_w, image_h), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (tile_w, image_h), "#eeeeee")
            px = (tile_w - image.width) // 2
            py = (image_h - image.height) // 2
            canvas.paste(image, (px, py))
            draw_box = ImageDraw.Draw(canvas)
            # Boxes are normalized relative to the original image. EXIF-rotated
            # images are still shown for review; overlays flag any orientation mismatch.
            scale_x = image.width
            scale_y = image.height
            for box in entry["boxes"]:
                x1 = px + int(box["xmin"] * scale_x)
                x2 = px + int(box["xmax"] * scale_x)
                y1 = py + int(box["ymin"] * scale_y)
                y2 = py + int(box["ymax"] * scale_y)
                draw_box.rectangle((x1, y1, x2, y2), outline="#00aa44", width=3)
            sheet.paste(canvas, (x, y))
        draw.text((x, y + image_h + 5), f"{entry['image_id']} | egg boxes: {len(entry['boxes'])}", fill="black", font=font)

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-images", type=int, default=0, help="Optional limit on cached images to inspect; 0 means all")
    args = parser.parse_args()

    paths = repo_paths(Path(__file__))
    print(f"Repository: {paths['root']}")
    print(f"Detection CSV: {paths['detections']}")
    print(f"Image metadata CSV: {paths['image_info']}")

    cached_images = find_cached_images(paths["images"])
    if args.max_images > 0:
        cached_images = dict(list(cached_images.items())[:args.max_images])
    cached_ids = set(cached_images)
    print(f"Cached JPEGs discovered: {len(cached_images)}")

    print("Scanning the large detection CSV (streaming; no full-file memory load)...")
    egg_boxes, matching_rows, invalid_rows = read_egg_boxes(paths["detections"], cached_ids)
    eligible_ids = set(egg_boxes)
    print(f"Egg annotation rows matching cached images: {matching_rows}")
    print(f"Valid egg boxes: {sum(len(v) for v in egg_boxes.values())}")
    print(f"Invalid matching rows skipped: {invalid_rows}")
    print(f"Cached images with at least one Egg (Food) box: {len(eligible_ids)}")

    if not eligible_ids:
        print("No cached images had a valid Egg (Food) annotation. Nothing was exported.")
        return 2

    metadata = read_image_metadata(paths["image_info"], eligible_ids)
    existing_reviews = load_existing_review(paths["inspection"])
    paths["raw"].mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    inspection_rows: list[dict[str, Any]] = []
    annotation_rows: list[dict[str, Any]] = []
    missing_metadata: list[str] = []
    copied_count = 0

    for image_id in sorted(eligible_ids):
        source_path = cached_images[image_id]
        try:
            # Verify the source stream first, then reopen to inspect oriented dimensions.
            with Image.open(source_path) as probe:
                probe.verify()
            with Image.open(source_path) as img:
                img = ImageOps.exif_transpose(img)
                width, height = img.size
        except OSError as exc:
            print(f"WARNING: unreadable cached image {image_id}: {exc}")
            continue

        meta = metadata.get(image_id, {})
        if not meta:
            missing_metadata.append(image_id)

        destination = paths["raw"] / source_path.name
        if not destination.exists():
            shutil.copy2(source_path, destination)
            copied_count += 1
        else:
            # Do not overwrite a previously exported or manually modified file.
            if destination.stat().st_size != source_path.stat().st_size:
                print(f"WARNING: existing raw file differs in size; preserved it: {destination}")

        try:
            actual_md5 = md5_base64_file(destination)
            expected_md5 = meta.get("OriginalMD5", "")
            md5_match: bool | None = (actual_md5 == expected_md5) if expected_md5 else None
        except OSError:
            md5_match = None

        sidecar = {
            "image_id": image_id,
            "dataset": "Open Images V7",
            "subset": meta.get("Subset", "train"),
            "label_mid": EGG_MID,
            "label_name": EGG_DISPLAY_NAME,
            "image_path": str(destination.relative_to(paths["root"])).replace("\\", "/"),
            "width": width,
            "height": height,
            "original_url": meta.get("OriginalURL", ""),
            "original_landing_url": meta.get("OriginalLandingURL", ""),
            "license_url": meta.get("License", ""),
            "author": meta.get("Author", ""),
            "author_profile_url": meta.get("AuthorProfileURL", ""),
            "title": meta.get("Title", ""),
            "original_size": meta.get("OriginalSize", ""),
            "original_md5_base64": meta.get("OriginalMD5", ""),
            "computed_md5_base64": actual_md5,
            "original_md5_matches": md5_match,
            "rotation_degrees": meta.get("Rotation", ""),
            "detection_boxes_normalized": egg_boxes[image_id],
        }
        sidecar_path = paths["raw"] / f"{image_id}_meta.json"
        # Always refresh machine provenance; human review decisions live in the CSV.
        sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")

        previous = existing_reviews.get(image_id, {})
        filename = destination.name
        boxes = egg_boxes[image_id]
        inspection_rows.append({
            "image_id": image_id,
            "filename": filename,
            "width": width,
            "height": height,
            "original_url": meta.get("OriginalURL", ""),
            "original_landing_url": meta.get("OriginalLandingURL", ""),
            "license": meta.get("License", ""),
            "author": meta.get("Author", ""),
            "author_profile_url": meta.get("AuthorProfileURL", ""),
            "title": meta.get("Title", ""),
            "subset": meta.get("Subset", "train"),
            "version": "v7",
            "egg_detection_count": len(boxes),
            "filter_decision": previous.get("filter_decision", ""),
            "review_status": previous.get("review_status", "pending"),
            "md5_matches_original": md5_match,
        })
        for box_index, box in enumerate(boxes):
            annotation_rows.append({"image_id": image_id, "box_index": box_index, **box})

        entries.append({"image_id": image_id, "source_path": destination, "boxes": boxes})

    inspection_fields = [
        "image_id", "filename", "width", "height", "original_url", "original_landing_url",
        "license", "author", "author_profile_url", "title", "subset", "version",
        "egg_detection_count", "filter_decision", "review_status", "md5_matches_original",
    ]
    # Merge old review rows for images not present in this cache; never discard review work.
    current_ids = {row["image_id"] for row in inspection_rows}
    for old_id, old_row in existing_reviews.items():
        if old_id not in current_ids:
            inspection_rows.append({field: old_row.get(field, "") for field in inspection_fields})
    inspection_rows.sort(key=lambda row: row.get("image_id", ""))
    save_csv(paths["inspection"], inspection_fields, inspection_rows)

    annotation_fields = [
        "image_id", "box_index", "label_mid", "label_name", "source", "confidence",
        "xmin", "xmax", "ymin", "ymax", "is_occluded", "is_truncated", "is_group_of",
        "is_depiction", "is_inside",
    ]
    save_csv(paths["filtered_annotations"], annotation_fields, annotation_rows)
    make_contact_sheet(entries, paths["contact_sheet"])

    print("\n=== CACHED EGG EXPORT SUMMARY ===")
    print(f"Cached JPEGs discovered: {len(cached_images)}")
    print(f"Images with valid Egg (Food) boxes exported: {len(entries)}")
    print(f"Raw JPEG files newly copied: {copied_count}")
    print(f"Egg detection boxes exported: {len(annotation_rows)}")
    print(f"Images missing provenance metadata: {len(missing_metadata)}")
    if missing_metadata:
        print("Missing metadata IDs: " + ", ".join(missing_metadata))
    print(f"Raw folder: {paths['raw']}")
    print(f"Inspection CSV: {paths['inspection']}")
    print(f"Filtered detection boxes CSV: {paths['filtered_annotations']}")
    print(f"Contact sheet: {paths['contact_sheet']}")
    print("Segmentation: deferred; this script did not inspect or download masks.")
    print("No FiftyOne dataset/database service was started by this exporter.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, ValueError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
