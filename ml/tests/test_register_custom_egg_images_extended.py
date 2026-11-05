"""Extended tests for register_custom_egg_images covering PNG, WebP, capture ID uniqueness, metadata fields, CSV headers, duplicate detection, side‑car missing, source immutability, unsafe specimen IDs, and view handling.

All image creation uses the pytest ``tmp_path`` fixture to avoid touching the repository root.
"""

import os
import csv
import json
import shutil
from pathlib import Path
import pytest
from PIL import Image

# Helper to create an image at a given path.
def _create_image(path: Path, fmt: str = "JPEG", colour: str = None) -> Path:
    # Generate a deterministic colour based on the file path if not provided, ensuring distinct images for different paths.
    if colour is None:
        # Simple hash to produce an RGB tuple.
        hash_val = sum(ord(c) for c in str(path)) % 256
        colour = (hash_val, (hash_val * 2) % 256, (hash_val * 3) % 256)
    img = Image.new("RGB", (100, 100), color=colour)
    img.save(path, fmt)
    return path
    img = Image.new("RGB", (100, 100), color=colour)
    img.save(path, fmt)
    return path

# Helper to read CSV files.
def _read_csv(path: Path):
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

# ---------------------------------------------------------------------------
# Basic registration tests for PNG and WebP
# ---------------------------------------------------------------------------

def test_register_valid_png(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(tmp_path / "temp.png", fmt="PNG")
    meta = reg.register_image(source=src, specimen_id="EGG005", view="side", custom_root=custom_root)
    assert (custom_root / "raw" / "EGG005" / f"{meta['capture_id']}.png").exists()
    src.unlink()

def test_register_valid_webp(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(tmp_path / "temp.webp", fmt="WEBP")
    meta = reg.register_image(source=src, specimen_id="EGG006", view="oblique", custom_root=custom_root)
    assert (custom_root / "raw" / "EGG006" / f"{meta['capture_id']}.webp").exists()
    src.unlink()

# ---------------------------------------------------------------------------
# Capture ID uniqueness test (different image content)
# ---------------------------------------------------------------------------

def test_unique_capture_ids(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    src1 = _create_image(tmp_path / "c1.jpg", colour="red")
    src2 = _create_image(tmp_path / "c2.jpg", colour="blue")
    meta1 = reg.register_image(source=src1, specimen_id="EGG007", view="top", custom_root=custom_root)
    meta2 = reg.register_image(source=src2, specimen_id="EGG007", view="side", custom_root=custom_root)
    assert meta1["capture_id"] != meta2["capture_id"]
    src1.unlink(); src2.unlink()

# ---------------------------------------------------------------------------
# JSON fields validation
# ---------------------------------------------------------------------------

def test_json_fields_present(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(tmp_path / "temp2.jpg")
    meta = reg.register_image(
        source=src,
        specimen_id="EGG008",
        view="closeup",
        lighting="studio",
        background="white",
        photographer="Bob",
        captured_at="2023-01-01T12:00:00",
        provenance="lab",
        license="CC0",
        custom_root=custom_root,
    )
    required = [
        "specimen_id", "capture_id", "original_filename", "stored_filename",
        "sha256", "image_width", "image_height", "format", "view",
        "captured_at", "registered_at", "lighting", "background",
        "photographer", "provenance", "license", "review_status",
    ]
    for f in required:
        assert f in meta
    src.unlink()

# ---------------------------------------------------------------------------
# CSV header checks and duplicate specimen prevention
# ---------------------------------------------------------------------------

def test_csv_headers_and_no_duplicate_specimen(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    src1 = _create_image(tmp_path / "h1.jpg")
    reg.register_image(source=src1, specimen_id="EGG009", view="top", custom_root=custom_root)
    src2 = _create_image(tmp_path / "h2.jpg")
    reg.register_image(source=src2, specimen_id="EGG009", view="side", custom_root=custom_root)
    images = _read_csv(custom_root / "manifests" / "images.csv")
    specimens = _read_csv(custom_root / "manifests" / "specimens.csv")
    expected_image_keys = {
        "image_id", "specimen_id", "stored_filename", "view", "sha256",
        "width", "height", "format", "captured_at", "registered_at",
        "lighting", "background", "photographer", "provenance", "license", "review_status",
    }
    expected_specimen_keys = {"specimen_id", "registered_at", "notes"}
    assert set(images[0].keys()) == expected_image_keys
    assert set(specimens[0].keys()) == expected_specimen_keys
    assert len([s for s in specimens if s["specimen_id"] == "EGG009"]) == 1
    src1.unlink(); src2.unlink()

# ---------------------------------------------------------------------------
# Duplicate detection tests
# ---------------------------------------------------------------------------

def test_destination_not_overwritten(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(tmp_path / "dup1.jpg")
    meta = reg.register_image(source=src, specimen_id="EGG010", view="top", custom_root=custom_root)
    src2 = _create_image(tmp_path / "dup2.jpg")
    shutil.copy2(src, src2)
    with pytest.raises(reg.DuplicateImageError):
        reg.register_image(source=src2, specimen_id="EGG010", view="side", custom_root=custom_root)
    src.unlink(); src2.unlink()

def test_duplicate_hash_detection_when_sidecar_missing(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(tmp_path / "dh1.jpg")
    meta = reg.register_image(source=src, specimen_id="EGG011", view="top", custom_root=custom_root)
    json_path = custom_root / "metadata" / "EGG011" / f"{meta['capture_id']}.json"
    json_path.unlink()
    with pytest.raises(reg.DuplicateImageError):
        reg.register_image(source=src, specimen_id="EGG011", view="side", custom_root=custom_root)
    src.unlink()

# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

def test_source_unchanged(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(tmp_path / "orig.jpg")
    original_bytes = src.read_bytes()
    reg.register_image(source=src, specimen_id="EGG012", view="top", custom_root=custom_root)
    assert src.read_bytes() == original_bytes
    src.unlink()

def test_unsafe_specimen_id_rejected(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(tmp_path / "badid.jpg")
    with pytest.raises(reg.RegistrationError):
        reg.register_image(source=src, specimen_id="../evil", view="top", custom_root=custom_root)
    src.unlink()

def test_invalid_view_allowed(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(tmp_path / "badview.jpg")
    meta = reg.register_image(source=src, specimen_id="EGG013", view="invalid_view", custom_root=custom_root)
    assert meta["view"] == "invalid_view"
    src.unlink()

# ---------------------------------------------------------------------------
# Unsupported format and corrupt image tests
# ---------------------------------------------------------------------------

def test_unsupported_format(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    dummy = tmp_path / "bad.tiff"
    dummy.write_bytes(b"not an image")
    with pytest.raises(reg.RegistrationError) as exc:
        reg.register_image(source=dummy, specimen_id="EGG003", view="oblique", custom_root=custom_root)
    assert "Unsupported file extension" in str(exc.value)
    dummy.unlink()

def test_corrupt_image(custom_root, tmp_path):
    from ml.scripts import register_custom_egg_images as reg
    corrupt = tmp_path / "corrupt.jpg"
    corrupt.write_bytes(b"this is not a real jpeg file")
    with pytest.raises(reg.RegistrationError) as exc:
        reg.register_image(source=corrupt, specimen_id="EGG004", view="closeup", custom_root=custom_root)
    assert "Corrupt or unreadable image" in str(exc.value)
    corrupt.unlink()
