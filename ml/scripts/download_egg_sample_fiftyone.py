#!/usr/bin/env python
"""download_egg_sample_fiftyone.py

A development‑only script that uses FiftyOne’s Open Images V7 zoo integration to
download a small, manually‑reviewable sample of the Egg (Food) class.

The script now follows the exact API of FiftyOne 0.22+ where
``foi.get_classes(version="v7")`` returns **a list of display‑name strings**.
We therefore perform a two‑step verification:

1. Confirm that the display name ``"Egg (Food)"`` is present in the class list.
2. Parse the official ``class-descriptions.csv`` (cached under ``ml/data/tmp``)
   to obtain the MID and ensure it matches ``/m/0c9ph5``.

Only after successful verification does the script proceed to a **smoke‑test
download of five images** (you can raise ``max_samples`` to 100 for the full
run).

It also prints useful environment information (FiftyOne version, Python
version, verified class name, MID, and segmentation availability) before
any network activity.
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
    ``"Egg (Food)"``. No MID information is included.
    """
    return foi.get_classes(version="v7")

def _load_class_descriptions() -> Dict[str, str]:
    """Parse the official ``class-descriptions.csv`` and return a dict MID → name.

    The CSV is expected at ``ml/data/tmp/class-descriptions.csv``. It is a
    standard CSV with two columns: ``MID,DisplayName``. We use ``csv.reader``
    which correctly handles quoted fields and commas inside the display name.
    """
    csv_path = DATA_ROOT / "tmp" / "class-descriptions.csv"
    if not csv_path.exists():
        raise RuntimeError(
            f"class-descriptions.csv not found at {csv_path}. "
            "Please download it from the Open Images V7 release page."
        )
    mapping: Dict[str, str] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) != 2:
                continue
            mid, name = row[0].strip(), row[1].strip()
            mapping[mid] = name
    return mapping

def _verify_egg_class() -> str:
    """Confirm that the Egg (Food) class exists and return its display name.

    Returns the exact display name (should be ``"Egg (Food)"``). Raises if not
    found.
    """
    target_name = "Egg (Food)"
    class_list = _load_detection_class_list()
    if target_name not in class_list:
        # Provide a helpful hint with any class containing the word "egg"
        matches = [c for c in class_list if "egg" in c.lower()]
        raise RuntimeError(
            f"Egg class not found. Available classes containing 'egg': {matches}"
        )
    print(f"✅ Verified detection class display name: '{target_name}'")
    return target_name

def _get_mid_for_name(display_name: str) -> str:
    """Lookup the MID for a given display name using the official CSV mapping.
    Raises if the name is not present.
    """
    mapping = _load_class_descriptions()
    for mid, name in mapping.items():
        if name == display_name:
            return mid
    raise RuntimeError(f"MID for display name '{display_name}' not found in class-descriptions.csv")

def _egg_has_segmentation() -> bool:
    """Determine whether the Egg MID appears in the V7 segmentation class list.

    We load a tiny segmentation dataset (max 5 samples) just to obtain the set of
    segment IDs that the zoo knows about, then check for the MID.
    """
    # Ensure the zoo directory is inside the repository to avoid global clutter
    fo.config.dataset_zoo_dir = str(DATA_ROOT / "fiftyone_cache")
    seg_dataset = foz.load_zoo_dataset(
        "open-images-v7",
        split="train",
        label_types=["segmentations"],
        max_samples=5,
        shuffle=False,
        seed=1,
    )
    seg_ids = set()
    for sample in seg_dataset:
        for seg in sample.segmentations.iter_segments():
            seg_ids.add(seg.id)
    return "/m/0c9ph5" in seg_ids

def _download_detection_samples(display_name: str, max_samples: int = 5) -> fo.Dataset:
    """Download a small number of training images that contain the Egg class.

    Parameters
    ----------
    display_name: str
        The exact detection class display name (e.g., "Egg (Food)").
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
    # 1️⃣ Verify class name and retrieve MID
    # ---------------------------------------------------------------
    try:
        egg_display_name = _verify_egg_class()
    except Exception as exc:
        sys.exit(f"❌ Class verification failed: {exc}")
    try:
        egg_mid = _get_mid_for_name(egg_display_name)
    except Exception as exc:
        sys.exit(f"❌ MID lookup failed: {exc}")
    print(f"✅ MID for '{egg_display_name}' is {egg_mid}")

    # ---------------------------------------------------------------
    # 2️⃣ Check segmentation availability for the same MID
    # ---------------------------------------------------------------
    seg_available = _egg_has_segmentation()
    print(f"Segmentation availability for MID {egg_mid}: {seg_available}")

    # ---------------------------------------------------------------
    # 3️⃣ Smoke‑test download (5 images)
    # ---------------------------------------------------------------
    dataset = _download_detection_samples(egg_display_name, max_samples=5)
    samples = list(dataset)
    print(f"🖼️  Smoke‑test downloaded {len(samples)} samples.")

    # ---------------------------------------------------------------
    # 4️⃣ Export raw images & side‑car metadata
    # ---------------------------------------------------------------
    _export_raw_and_metadata(samples)

    # ---------------------------------------------------------------
    # 5️⃣ Write / update inspection CSV (preserve prior decisions)
    # ---------------------------------------------------------------
    _write_inspection_csv(samples)

    # ---------------------------------------------------------------
    # 6️⃣ Build contact‑sheet for manual review
    # ---------------------------------------------------------------
    _create_contact_sheet(samples)

    # ---------------------------------------------------------------
    # 7️⃣ Summary
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
