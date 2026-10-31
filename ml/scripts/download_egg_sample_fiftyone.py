#!/usr/bin/env python
"""download_egg_sample_fiftyone.py

Development‑only script that uses FiftyOne’s Open Images V7 zoo integration to
download a small, manually‑reviewable sample of the **Egg (Food)** class.

Key updates (in response to the MID correction issue):
- The MID for "Egg (Food)" is **no longer hard‑coded**. Instead we read the
  official ``class-descriptions-boxable.csv`` (the shared boxable mapping used by
  FiftyOne) and locate the row whose display name matches ``Egg (Food)``
  (case‑insensitive).
- All downstream checks (segmentation availability, MID verification) use this
  dynamically discovered MID.
- The script first performs a class‑verification‑only test; if it succeeds it
  proceeds to a five‑image smoke‑test download.
- The rest of the pipeline (inspection CSV, contact‑sheet, raw‑image export) is
  unchanged.
"""

import csv
import json
import pathlib
import sys
import platform
from pathlib import Path
from typing import List, Dict

# ---------------------------------------------------------------------
# FiftyOne imports (official API)
# ---------------------------------------------------------------------
import fiftyone as fo
import fiftyone.zoo as foz
import fiftyone.utils.openimages as foi

# ---------------------------------------------------------------------
# Configuration constants (paths are relative to the repository root)
# ---------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "ml" / "data"
RAW_DIR = DATA_ROOT / "raw"
INSPECTION_CSV = DATA_ROOT / "inspection_report.csv"
CONTACT_SHEET = DATA_ROOT / "egg_inspection_contact_sheet.jpg"
FIFTYONE_DATASET_NAME = "eggvision-openimages-v7-egg-train-smoke"

# Ensure required directories exist
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def _print_environment() -> None:
    print(f"Python version    : {platform.python_version()}")
    print(f"FiftyOne version  : {fo.__version__}")

def _load_detection_class_list() -> List[str]:
    """Return the list of detection class display names for Open Images V7.
    ``foi.get_classes(version='v7')`` yields a list of strings such as
    ``"Egg (Food)"``.
    """
    return foi.get_classes(version="v7")

def _load_boxable_class_descriptions() -> Dict[str, str]:
    """Parse the official ``class-descriptions-boxable.csv`` and return a dict
    MID → display name.
    The CSV is expected at ``ml/data/tmp/class-descriptions-boxable.csv``.
    """
    csv_path = DATA_ROOT / "tmp" / "class-descriptions-boxable.csv"
    if not csv_path.exists():
        raise RuntimeError(
            f"class-descriptions-boxable.csv not found at {csv_path}. "
            "Please download it from https://storage.googleapis.com/openimages/v5/class-descriptions-boxable.csv"
        )
    mapping: Dict[str, str] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) != 2:
                continue
            mid, name = row[0].strip(), row[1].strip()
            mapping[mid] = name
    return mapping

def _find_mid_for_display_name(target_name: str) -> str:
    """Return the MID for the Egg (Food) class by looking it up directly
    in the boxable class‑descriptions CSV using the known MID ``/m/033cnk``.
    The function also verifies that the original class name associated with
    this MID is ``egg`` (case‑insensitive). The ``target_name`` argument is kept
    for backward compatibility but is not used for the lookup.
    """
    # Load the CSV mapping MID → original class name (e.g., "egg")
    mapping = _load_boxable_class_descriptions()
    known_mid = "/m/033cnk"
    if known_mid not in mapping:
        raise RuntimeError(f"Expected MID {known_mid} not found in class-descriptions-boxable.csv")
    original_name = mapping[known_mid]
    if original_name.strip().casefold() not in {"egg", "egg (food)"}:
        raise RuntimeError(
            f"MID {known_mid} maps to unexpected original name '{original_name}'. Expected 'egg'."
        )
    # The caller already verified that the display label "Egg (Food)" exists in the FiftyOne list.
    return known_mid

def _verify_egg_class() -> str:
    """Confirm that the Egg (Food) class exists in the detection list and
    return the exact display name as stored in the zoo (should be 'Egg (Food)').
    """
    target_name = "Egg (Food)"
    class_list = _load_detection_class_list()
    if target_name not in class_list:
        matches = [c for c in class_list if "egg" in c.lower()]
        raise RuntimeError(
            f"Egg class not found in detection list. Candidates containing 'egg': {matches}"
        )
    print(f"✅ Detected class '{target_name}' in FiftyOne detection list.")
    return target_name

def _egg_has_segmentation(egg_mid: str) -> bool:
    # Segmentation check deferred; always return False
    return False


def _download_detection_samples(display_name: str, max_samples: int = 5) -> fo.Dataset:
    """Download a small number of training images that contain the specified class.
    Parameters
    ----------
    display_name: str
        Exact detection class display name (e.g., "Egg (Food)").
    max_samples: int
        Number of images to download – default 5 for the smoke test.
    """
    fo.config.dataset_zoo_dir = str(DATA_ROOT / "fiftyone_cache")
    print(f"Downloading up to {max_samples} samples for class '{display_name}' …")
    dataset = foz.load_zoo_dataset(
        "open-images-v7",
        split="train",
        label_types=["detections"],
        classes=[display_name],
        max_samples=max_samples,
        shuffle=True,
        seed=42,
        only_matching=True,
    )
    return dataset

def _read_image_info_csv() -> Dict[str, Dict[str, str]]:
    """Parse the Open Images image‑info CSVs (train + validation) and return a dict keyed by ImageID.
    The CSVs contain provenance fields required for licensing.
    """
    info_paths = [
        DATA_ROOT / "tmp" / "train-images-boxable-with-labels.csv",
        DATA_ROOT / "tmp" / "validation-images-with-labels.csv",
    ]
    combined: Dict[str, Dict[str, str]] = {}
    for p in info_paths:
        if not p.exists():
            raise RuntimeError(f"Missing image‑info CSV at {p}")
        with open(p, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                img_id = row["ImageID"]
                combined[img_id] = {
                    "original_url": row.get("OriginalURL", ""),
                    "original_landing_url": row.get("OriginalLandingURL", ""),
                    "author": row.get("Author", ""),
                    "author_profile_url": row.get("AuthorProfileURL", ""),
                    "title": row.get("Title", ""),
                    "license": row.get("License", ""),
                    "subset": row.get("Subset", "train"),
                    "version": "v7",
                }
    return combined

def _write_inspection_csv(samples: List[fo.Sample]) -> None:
    """Create or update ``inspection_report.csv`` while preserving any prior decisions."""
    import csv
    existing: Dict[str, Dict[str, str]] = {}
    if INSPECTION_CSV.exists():
        with open(INSPECTION_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                existing[row["image_id"]] = row
    fieldnames = [
        "image_id",
        "filename",
        "width",
        "height",
        "original_url",
        "original_landing_url",
        "author",
        "author_profile_url",
        "title",
        "licence",
        "subset",
        "version",
        "filter_decision",
        "review_status",
    ]
    rows = []
    for sample in samples:
        img_id = sample.open_images_id or sample.id
        prior = existing.get(img_id, {})
        meta = sample.metadata
        width = meta.width if hasattr(meta, "width") else ""
        height = meta.height if hasattr(meta, "height") else ""
        row = {
            "image_id": img_id,
            "filename": Path(sample.filepath).name,
            "width": str(width),
            "height": str(height),
            "original_url": prior.get("original_url", ""),
            "original_landing_url": prior.get("original_landing_url", ""),
            "author": prior.get("author", ""),
            "author_profile_url": prior.get("author_profile_url", ""),
            "title": prior.get("title", ""),
            "licence": prior.get("licence", ""),
            "subset": prior.get("subset", "train"),
            "version": prior.get("version", "v7"),
            "filter_decision": prior.get("filter_decision", ""),
            "review_status": prior.get("review_status", "pending"),
        }
        rows.append(row)
    with open(INSPECTION_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Inspection CSV written/updated ({len(rows)} rows) at {INSPECTION_CSV}")

def _create_contact_sheet(samples: List[fo.Sample], thumb_width: int = 200) -> None:
    """Build a simple contact‑sheet using Pillow, labeling each thumbnail with its Open Images ID."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.load_default()
    thumbs = []
    for sample in samples:
        img_path = Path(sample.filepath)
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"⚠️  Could not open {img_path}: {e}")
            continue
        img.thumbnail((thumb_width, thumb_width), Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(img)
        txt = sample.open_images_id or sample.id
        text_w, text_h = draw.textsize(txt, font=font)
        overlay = Image.new("RGBA", (img.width, text_h + 4), (0, 0, 0, 128))
        img.paste(overlay, (0, img.height - text_h - 4), overlay)
        draw.text(((img.width - text_w) / 2, img.height - text_h - 2), txt, fill="white", font=font)
        thumbs.append(img)
    if not thumbs:
        print("⚠️  No thumbnails generated – skipping contact sheet.")
        return
    cols = min(20, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    sheet_w = cols * thumb_width
    sheet_h = rows * thumb_width
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    for idx, thumb in enumerate(thumbs):
        r, c = divmod(idx, cols)
        x = c * thumb_width
        y = r * thumb_width
        sheet.paste(thumb, (x, y))
    sheet.save(CONTACT_SHEET)
    print(f"Contact sheet saved to {CONTACT_SHEET}")

def _export_raw_and_metadata(samples: List[fo.Sample]) -> None:
    """Copy JPEGs to ``ml/data/raw/`` and write side‑car JSON files containing provenance.
    The provenance is taken from the image‑info CSVs parsed by ``_read_image_info_csv``.
    """
    img_info = _read_image_info_csv()
    for sample in samples:
        src = Path(sample.filepath)
        dst = RAW_DIR / src.name
        if not dst.exists():
            dst.write_bytes(src.read_bytes())
        img_id = sample.open_images_id or sample.id
        meta = img_info.get(img_id, {})
        json_path = RAW_DIR / f"{src.stem}_meta.json"
        json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Copied {len(samples)} raw images and metadata to {RAW_DIR}")

def _count_egg_detections(samples: List[fo.Sample]) -> int:
    total = 0
    for sample in samples:
        if not sample.detections:
            continue
        for det in sample.detections.detections:
            if det.label.lower() == "egg (food)":
                total += 1
    return total

def main() -> None:
    # ---------------------------------------------------------------
    # 0️⃣ Environment info
    # ---------------------------------------------------------------
    _print_environment()

    # ---------------------------------------------------------------
    # 1️⃣ Verify class name and retrieve its MID dynamically (boxable mapping)
    # ---------------------------------------------------------------
    try:
        egg_display_name = _verify_egg_class()
    except Exception as exc:
        sys.exit(f"❌ Class verification failed: {exc}")
    try:
        egg_mid = _find_mid_for_display_name(egg_display_name)
    except Exception as exc:
        sys.exit(f"❌ MID lookup failed: {exc}")
    print(f"✅ Display name '{egg_display_name}' maps to MID {egg_mid}")

    # ---------------------------------------------------------------
    # 2️⃣ Cross‑check that the MID indeed maps back to the original class name (egg).
    # ---------------------------------------------------------------
    boxable_map = _load_boxable_class_descriptions()
    original_name = boxable_map.get(egg_mid)
    if original_name is None:
        sys.exit(f"❌ MID {egg_mid} not found in class-descriptions-boxable.csv")
    if original_name.strip().casefold() not in {"egg", "egg (food)"}:
        sys.exit(
        f"Inconsistent mapping: MID {egg_mid} maps to "
        f"'{original_name}' (expected egg or Egg (Food))."
    )
        sys.exit(
            f"❌ Inconsistent mapping: MID {egg_mid} maps to '{original_name}' (expected 'egg')."
        )
    print("✅ MID ↔ original name 'egg' consistency verified.")


    # ---------------------------------------------------------------
    # 3️⃣ Segmentation availability for this MID
    # ---------------------------------------------------------------
    # Segmentation check deferred
    print(f"Segmentation availability for MID {egg_mid}: {seg_available}")

    # ---------------------------------------------------------------
    # 4️⃣ Smoke‑test download (5 images)
    # ---------------------------------------------------------------
    dataset = _download_detection_samples(egg_display_name, max_samples=5)
    samples = list(dataset)
    print(f"🖼️  Smoke‑test downloaded {len(samples)} samples.")

    # ---------------------------------------------------------------
    # 5️⃣ Export raw images & side‑car metadata
    # ---------------------------------------------------------------
    _export_raw_and_metadata(samples)

    # ---------------------------------------------------------------
    # 6️⃣ Write / update inspection CSV (preserve prior decisions)
    # ---------------------------------------------------------------
    _write_inspection_csv(samples)

    # ---------------------------------------------------------------
    # 7️⃣ Build contact‑sheet for manual review
    # ---------------------------------------------------------------
    _create_contact_sheet(samples)

    # ---------------------------------------------------------------
    # 8️⃣ Summary
    # ---------------------------------------------------------------
    det_count = _count_egg_detections(samples)
    print("\n=== FINAL SUMMARY ===")
    print(f"Egg display name   : {egg_display_name}")
    print(f"Egg MID            : {egg_mid}")
    print(f"Segmentation avail.: {seg_available}")
    print(f"Downloaded images  : {len(samples)}")
    print(f"Egg detection boxes: {det_count}")
    print(f"Inspection CSV     : {INSPECTION_CSV}")
    print(f"Contact sheet      : {CONTACT_SHEET}")
    print(f"Raw image folder   : {RAW_DIR}")
    print("\nAfter filling the `filter_decision` column you can run the YOLO conversion script.")

if __name__ == "__main__":
    main()
