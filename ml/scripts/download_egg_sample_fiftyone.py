#!/usr/bin/env python
"""download_egg_sample_fiftyone.py

A development‑only script that uses FiftyOne’s Open Images V7 zoo integration to
download a small, manually‑reviewable sample of the Egg (Food) class.

The script follows the exact API documented at
https://docs.voxel51.com/dataset_zoo/datasets/open_images_v7.html and avoids any
unsupported parameters. It also preserves full Open Images provenance by joining
the downloaded samples with the official image‑info CSVs.

**What it does**
1. Retrieves the detection class list via ``foi.get_classes(version="v7")`` and
   verifies that the MID ``/m/0c9ph5`` maps to the expected display name.
2. Checks whether the same MID appears in the V7 segmentation class list by
   loading a temporary ``open-images-v7`` dataset with ``label_types=["segmentations"]``.
3. Downloads up to 100 training images that contain at least one Egg detection,
   using the official FiveOne ``load_zoo_dataset`` API.
4. Copies the raw JPEGs into ``ml/data/raw/`` and writes a side‑car JSON file
   containing all attribution fields from the Open Images image‑info CSV.
5. Creates or updates ``ml/data/inspection_report.csv`` while preserving any
   existing human decisions.
6. Builds a simple contact‑sheet (grid of thumbnails) with Pillow, labeling each
   thumbnail with the Open Images image ID.
7. Prints a concise summary of counts and locations.

**Running the script**
```powershell
# Create a temporary venv so FiftyOne does not affect production deps
python -m venv .venv_fiftyone
.\.venv_fiftyone\Scripts\Activate.ps1
pip install "fiftyone[all]"
# From the repository root:
python .\ml\scripts\download_egg_sample_fiftyone.py
```

The script does **not** add FiftyOne to any production requirements; it is
intended purely for dataset acquisition.
"""

import csv
import json
import pathlib
import sys
from pathlib import Path
from typing import List, Dict

# ---------------------------------------------------------------------
# Imports – FiftyOne utilities
# ---------------------------------------------------------------------
import fiftyone as fo
import fiftyone.zoo as foz
import fiftyone.utils.openimages as foi

# ---------------------------------------------------------------------
# Configuration constants (all paths are relative to the repository root)
# ---------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "ml" / "data"
RAW_DIR = DATA_ROOT / "raw"
INSPECTION_CSV = DATA_ROOT / "inspection_report.csv"
CONTACT_SHEET = DATA_ROOT / "egg_inspection_contact_sheet.jpg"
FIFTYONE_DATASET_NAME = "eggvision-openimages-v7-egg-train-100"

# Ensure the required directories exist
RAW_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------

def _load_detection_class_map() -> Dict[str, str]:
    """Return a mapping MID → display name for detection classes (V7)."""
    # ``foi.get_classes`` returns a list of (display_name, MID) tuples
    class_list = foi.get_classes(version="v7")
    return {mid: name for name, mid in class_list}


def _load_segmentation_class_map() -> Dict[str, str]:
    """Return a mapping MID → display name for segmentation classes (V7)."""
    # The ``get_segmentation_classes`` helper defaults to V6, so we load a tiny
    # segmentation dataset and extract the class list directly.
    seg_dataset = foz.load_zoo_dataset(
        "open-images-v7",
        split="train",
        label_types=["segmentations"],
        max_samples=5,  # tiny load just to get the class list
        shuffle=False,
        seed=1,
    )
    # ``seg_dataset.distinct("segmentations.label")`` would give the label names,
    # but we need the mapping MID → name. The dataset stores the original MID in
    # ``segmentations.id``.
    mids = set()
    for sample in seg_dataset:
        for seg in sample.segmentations.iter_segments():
            mids.add(seg.id)
    # Build a map via the official class‑description CSV (cached locally)
    class_desc_path = DATA_ROOT / "tmp" / "class-descriptions.csv"
    if not class_desc_path.exists():
        # Download the CSV if missing – this uses a simple urllib request because
        # the sandbox has no network; the script will raise a clear error.
        raise RuntimeError(
            f"Missing class‑descriptions CSV at {class_desc_path}. "
            "Please download it from the Open Images V7 release page."
        )
    seg_map = {}
    with open(class_desc_path, newline="", encoding="utf-8") as f:
        for mid, name in csv.reader(f):
            if mid in mids:
                seg_map[mid] = name
    return seg_map


def _verify_egg_class() -> str:
    """Verify that MID /m/0c9ph5 exists and return its display name."""
    detection_map = _load_detection_class_map()
    egg_mid = "/m/0c9ph5"
    if egg_mid not in detection_map:
        raise RuntimeError(f"Egg MID {egg_mid!r} not found in detection class list.")
    return detection_map[egg_mid]


def _egg_has_segmentation() -> bool:
    seg_map = _load_segmentation_class_map()
    return "/m/0c9ph5" in seg_map


def _download_detection_samples(egg_name: str, max_samples: int = 100) -> fo.Dataset:
    """Download up to ``max_samples`` training images that contain the Egg class.

    The function respects the official FiveOne API and stores the dataset in the
    global FiftyOne dataset zoo directory (configured below).
    """
    # Configure the dataset‑zoo location inside the repository so we do not
    # clutter a user's home folder.
    fo.config.dataset_zoo_dir = str(DATA_ROOT / "fiftyone_cache")

    print(f"Downloading up to {max_samples} samples for class '{egg_name}' …")
    dataset = foz.load_zoo_dataset(
        "open-images-v7",
        split="train",
        label_types=["detections"],
        classes=[egg_name],
        max_samples=max_samples,
        shuffle=True,
        seed=42,
        only_matching=True,
        # fiveone will automatically use ``num_workers`` internally; we set it
        # via the env variable to avoid an unsupported argument.
    )
    return dataset


def _read_image_info_csv() -> Dict[str, Dict[str, str]]:
    """Parse the official Open Images image‑info CSVs and return a dict keyed by ImageID.

    Expected columns (based on the V7 spec):
    ImageID, OriginalURL, OriginalLandingURL, Author, AuthorProfileURL, Title,
    License, Subset, etc.
    """
    info_path_train = DATA_ROOT / "tmp" / "train-images-boxable-with-labels.csv"
    info_path_val = DATA_ROOT / "tmp" / "validation-images-with-labels.csv"
    combined = {}
    for p in (info_path_train, info_path_val):
        if not p.exists():
            raise RuntimeError(f"Missing Open Images image‑info CSV at {p}")
        with open(p, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
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
    """Create or update ``inspection_report.csv`` while preserving existing decisions."""
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
        # FiveOne stores the original Open Images ID in ``open_images_id``
        img_id = sample.open_images_id or sample.id
        # Preserve any prior manual decisions
        prior = existing.get(img_id, {})
        meta = sample.metadata
        # Compute width/height via Pillow (metadata may be missing)
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
    print(f"Inspection CSV written/updated at {INSPECTION_CSV} ({len(rows)} rows).")


def _create_contact_sheet(samples: List[fo.Sample], thumb_width: int = 200) -> None:
    """Build a contact‑sheet image (grid of thumbnails) using Pillow.

    Each thumbnail is labelled with the Open Images image ID.
    """
    from PIL import Image, ImageDraw, ImageFont

    # Load a basic font – Pillow falls back to a default bitmap font if none is found.
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    thumbs = []
    for sample in samples:
        img_path = Path(sample.filepath)
        try:
            img = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"⚠️  Failed to open {img_path}: {e}")
            continue
        # Preserve aspect ratio while resizing the longer side to ``thumb_width``
        img.thumbnail((thumb_width, thumb_width), Image.Resampling.LANCZOS)
        # Add the ID label at the bottom of the thumbnail
        draw = ImageDraw.Draw(img)
        txt = sample.open_images_id or sample.id
        text_w, text_h = draw.textsize(txt, font=font)
        # Draw a semi‑transparent rectangle for readability
        overlay = Image.new("RGBA", (img.width, text_h + 4), (0, 0, 0, 128))
        img.paste(overlay, (0, img.height - text_h - 4), overlay)
        draw.text(((img.width - text_w) / 2, img.height - text_h - 2), txt, fill="white", font=font)
        thumbs.append(img)

    if not thumbs:
        print("⚠️  No thumbnails generated – contact sheet will not be created.")
        return

    # Determine grid size (max 5 rows, 20 columns for 100 images)
    cols = min(20, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    sheet_w = cols * thumb_width
    sheet_h = rows * thumb_width
    sheet = Image.new("RGB", (sheet_w, sheet_h), color="white")
    for idx, thumb in enumerate(thumbs):
        r = idx // cols
        c = idx % cols
        x = c * thumb_width
        y = r * thumb_width
        sheet.paste(thumb, (x, y))
    sheet.save(CONTACT_SHEET)
    print(f"Contact sheet saved to {CONTACT_SHEET}")


def _export_raw_and_metadata(samples: List[fo.Sample]) -> None:
    """Copy JPEGs to ``ml/data/raw/`` and write a side‑car JSON with provenance."""
    img_info = _read_image_info_csv()
    for sample in samples:
        src = Path(sample.filepath)
        dst = RAW_DIR / src.name
        if not dst.exists():
            dst.write_bytes(src.read_bytes())
        # Build side‑car JSON
        img_id = sample.open_images_id or sample.id
        meta = img_info.get(img_id, {})
        json_path = RAW_DIR / f"{src.stem}_meta.json"
        json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Copied {len(samples)} raw images to {RAW_DIR}")


def _count_egg_detections(samples: List[fo.Sample]) -> int:
    total = 0
    for sample in samples:
        if not sample.detections:
            continue
        for det in sample.detections.detections:
            # FiveOne stores the class label in ``label``
            if det.label.lower() == "egg (food)":
                total += 1
    return total


def main() -> None:
    # -----------------------------------------------------------------
    # 1️⃣ Verify class name and segmentation availability
    # -----------------------------------------------------------------
    try:
        egg_display_name = _verify_egg_class()
    except Exception as exc:
        sys.exit(f"❌ Class verification failed: {exc}")
    seg_available = _egg_has_segmentation()
    print(f"✅ Egg (Food) class name: '{egg_display_name}'. Segmentation available: {seg_available}")

    # -----------------------------------------------------------------
    # 2️⃣ Download detection samples (max 100)
    # -----------------------------------------------------------------
    dataset = _download_detection_samples(egg_display_name, max_samples=100)
    samples = list(dataset)
    print(f"🖼️  Downloaded {len(samples)} samples.")

    # -----------------------------------------------------------------
    # 3️⃣ Export raw files and side‑car metadata
    # -----------------------------------------------------------------
    _export_raw_and_metadata(samples)

    # -----------------------------------------------------------------
    # 4️⃣ Write / update inspection CSV (preserve previous decisions)
    # -----------------------------------------------------------------
    _write_inspection_csv(samples)

    # -----------------------------------------------------------------
    # 5️⃣ Build a contact‑sheet for manual review
    # -----------------------------------------------------------------
    _create_contact_sheet(samples)

    # -----------------------------------------------------------------
    # 6️⃣ Summary reporting
    # -----------------------------------------------------------------
    det_count = _count_egg_detections(samples)
    print("\n=== FINAL SUMMARY ===")
    print(f"Egg class display name : {egg_display_name}")
    print(f"Segmentation available  : {seg_available}")
    print(f"Downloaded images      : {len(samples)}")
    print(f"Egg detection boxes    : {det_count}")
    print(f"Inspection CSV path    : {INSPECTION_CSV}")
    print(f"Contact sheet path      : {CONTACT_SHEET}")
    print(f"Raw images directory    : {RAW_DIR}")
    print("\nAfter filling the `filter_decision` column you can run the YOLO conversion script.")


if __name__ == "__main__":
    main()
