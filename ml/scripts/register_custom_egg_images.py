'''register_custom_egg_images.py

Command‑line helper to safely register user‑provided photographs of individual, shell‑on chicken eggs
into the ``ml/data/custom_collection`` area.

The script validates the image, detects duplicates (by SHA‑256), copies it into a structured
``raw/<SPECIMEN_ID>/`` folder, creates a JSON side‑car with rich metadata, and updates the CSV
manifest files (``images.csv`` and ``specimens.csv``).

All paths are derived from the repository root (``REPO_ROOT``).  For testing a custom root can be
passed to :func:`register_image` so that the real project data are never touched.
'''  

import argparse
import csv
import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class RegistrationError(RuntimeError):
    """Base class for registration‑related errors."""

class DuplicateImageError(RegistrationError):
    """Raised when an image with the same SHA‑256 already exists in the collection."""

# ---------------------------------------------------------------------------
# Constants – derived from the repository layout
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CUSTOM_ROOT = REPO_ROOT / "ml" / "data" / "custom_collection"

RAW_ROOT = DEFAULT_CUSTOM_ROOT / "raw"
METADATA_ROOT = DEFAULT_CUSTOM_ROOT / "metadata"
MANIFESTS_ROOT = DEFAULT_CUSTOM_ROOT / "manifests"
IMAGES_CSV = MANIFESTS_ROOT / "images.csv"
SPECIMENS_CSV = MANIFESTS_ROOT / "specimens.csv"

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def compute_sha256(file_path: Path) -> str:
    """Return the hex SHA‑256 digest of *file_path*.
    """
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def load_existing_hashes(metadata_dir: Path) -> dict[str, Path]:
    """Return a mapping ``sha256 -> metadata_file`` for all JSON side‑cars in *metadata_dir*.
    The function walks the directory tree recursively because each specimen has its own sub‑folder.
    """
    hashes: dict[str, Path] = {}
    if not metadata_dir.exists():
        return hashes
    for json_file in metadata_dir.rglob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            h = data.get("sha256")
            if isinstance(h, str):
                hashes[h] = json_file
        except Exception:
            # Corrupt side‑car – ignore for duplicate detection
            continue
    return hashes

def next_capture_id(specimen_dir: Path, specimen_id: str, suffix: str) -> str:
    """Generate the next ``capture_id`` for *specimen_id* inside *specimen_dir*.
    Existing files are expected to follow the pattern ``{specimen_id}_{nnnn}{suffix}`` where
    ``nnnn`` is a zero‑padded integer.  The function returns a string like ``EGG001_0003``.
    """
    existing = [p for p in specimen_dir.iterdir() if p.is_file()]
    max_idx = 0
    for p in existing:
        stem = p.stem  # e.g. "EGG001_0002"
        if stem.startswith(f"{specimen_id}_"):
            try:
                idx = int(stem.split("_")[1])
                max_idx = max(max_idx, idx)
            except ValueError:
                continue
    next_idx = max_idx + 1
    return f"{specimen_id}_{next_idx:04d}"

def ensure_manifest(csv_path: Path, header: list[str]):
    """Create *csv_path* with *header* if it does not exist.
    """
    if not csv_path.parent.exists():
        csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not csv_path.exists():
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)

# ---------------------------------------------------------------------------
# Core registration logic (callable from tests)
# ---------------------------------------------------------------------------

def register_image(
    source: Path,
    specimen_id: str,
    view: str,
    lighting: Optional[str] = None,
    background: Optional[str] = None,
    photographer: Optional[str] = None,
    captured_at: Optional[str] = None,
    provenance: Optional[str] = None,
    license: Optional[str] = None,
    *,
    custom_root: Optional[Path] = None,
) -> dict:
    """Register *source* image into the custom collection.

    Parameters
    ----------
    source: Path
        Path to the original image file supplied by the user.
    specimen_id: str
        Identifier for the physical egg (e.g. ``EGG001``). Must be unique across specimens.
    view: str
        One of ``top, side, oblique, closeup, other``.
    lighting, background, photographer, captured_at, provenance, license:
        Optional free‑form metadata strings.
    custom_root: Path, optional
        Root of the custom collection. If omitted the default repository location is used.

    Returns
    -------
    dict
        The generated metadata dictionary (also written to a JSON side‑car).
    """
    # Resolve collection root
    root = Path(custom_root) if custom_root else DEFAULT_CUSTOM_ROOT
    raw_root = root / "raw"
    metadata_root = root / "metadata"
    manifests_root = root / "manifests"

    # -------------------------------------------------------------------
    # 1. Validate source image format
    # -------------------------------------------------------------------
    supported_exts = {".jpg", ".jpeg", ".png", ".webp"}
    if source.suffix.lower() not in supported_exts:
        raise RegistrationError(f"Unsupported file extension: {source.suffix}. Supported: {', '.join(supported_exts)}")
    try:
        with Image.open(source) as img:
            img.verify()  # verify integrity without loading pixel data
            width, height = img.width, img.height
            fmt = img.format
    except (UnidentifiedImageError, OSError) as e:
        raise RegistrationError(f"Corrupt or unreadable image file: {e}")

    # -------------------------------------------------------------------
    # 2. Compute SHA‑256 and check for duplicates
    # -------------------------------------------------------------------
    sha256 = compute_sha256(source)
    existing_hashes = load_existing_hashes(metadata_root)
    if sha256 in existing_hashes:
        raise DuplicateImageError(f"Duplicate image detected (SHA‑256={sha256}). Already registered in {existing_hashes[sha256]}")

    # -------------------------------------------------------------------
    # 3. Prepare destination paths
    # -------------------------------------------------------------------
    specimen_raw_dir = raw_root / specimen_id
    specimen_raw_dir.mkdir(parents=True, exist_ok=True)
    specimen_meta_dir = metadata_root / specimen_id
    specimen_meta_dir.mkdir(parents=True, exist_ok=True)

    capture_id = next_capture_id(specimen_raw_dir, specimen_id, source.suffix.lower())
    stored_filename = f"{capture_id}{source.suffix.lower()}"
    dest_path = specimen_raw_dir / stored_filename

    # -------------------------------------------------------------------
    # 4. Copy the file (preserve original timestamps)
    # -------------------------------------------------------------------
    shutil.copy2(source, dest_path)

    # -------------------------------------------------------------------
    # 5. Create metadata side‑car
    # -------------------------------------------------------------------
    now_iso = datetime.now().isoformat()
    metadata = {
        "specimen_id": specimen_id,
        "capture_id": capture_id,
        "original_filename": source.name,
        "stored_filename": stored_filename,
        "sha256": sha256,
        "image_width": width,
        "image_height": height,
        "format": fmt,
        "view": view,
        "captured_at": captured_at,
        "registered_at": now_iso,
        "lighting": lighting,
        "background": background,
        "photographer": photographer,
        "provenance": provenance,
        "license": license,
        "review_status": "pending",
    }
    meta_path = specimen_meta_dir / f"{capture_id}.json"
    meta_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    # -------------------------------------------------------------------
    # 6. Update CSV manifests
    # -------------------------------------------------------------------
    images_header = [
        "image_id",
        "specimen_id",
        "stored_filename",
        "view",
        "sha256",
        "width",
        "height",
        "format",
        "captured_at",
        "registered_at",
        "lighting",
        "background",
        "photographer",
        "provenance",
        "license",
        "review_status",
    ]
    ensure_manifest(IMAGES_CSV, images_header)

    with IMAGES_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            capture_id,
            specimen_id,
            stored_filename,
            view,
            sha256,
            width,
            height,
            fmt,
            captured_at or "",
            now_iso,
            lighting or "",
            background or "",
            photographer or "",
            provenance or "",
            license or "",
            "pending",
        ])

    # Specimens manifest – add a row if this specimen is new
    specimens_header = ["specimen_id", "registered_at", "notes"]
    ensure_manifest(SPECIMENS_CSV, specimens_header)
    # Check if specimen already present
    specimen_present = False
    with SPECIMENS_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("specimen_id") == specimen_id:
                specimen_present = True
                break
    if not specimen_present:
        with SPECIMENS_CSV.open("a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([specimen_id, now_iso, ""])

    print(f"✅ Registered {source.name} as {capture_id} (specimen {specimen_id})")
    return metadata

# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Register a custom egg photograph into the collection.")
    parser.add_argument("--source", required=True, type=Path, help="Path to the source image file.")
    parser.add_argument("--specimen", required=True, help="Specimen ID (e.g. EGG001).")
    parser.add_argument("--view", required=True, choices=["top", "side", "oblique", "closeup", "other"], help="View angle.")
    parser.add_argument("--lighting", help="Lighting description.")
    parser.add_argument("--background", help="Background description.")
    parser.add_argument("--photographer", help="Name of the photographer.")
    parser.add_argument("--captured_at", help="Timestamp when the photo was taken (ISO‑8601).")
    parser.add_argument("--provenance", help="Free‑form provenance note.")
    parser.add_argument("--license", help="License information.")
    return parser.parse_args(argv)


def main() -> None:
    args = _parse_args()
    try:
        register_image(
            source=args.source,
            specimen_id=args.specimen,
            view=args.view,
            lighting=args.lighting,
            background=args.background,
            photographer=args.photographer,
            captured_at=args.captured_at,
            provenance=args.provenance,
            license=args.license,
        )
    except RegistrationError as e:
        print(f"❌ Registration failed: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
