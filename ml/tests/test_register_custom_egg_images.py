'''test_register_custom_egg_images.py

import io
import csv
import json
import os
from pathlib import Path
import pytest
from PIL import Image

# The fixtures in conftest will patch the module constants to point at a temporary directory.

def _create_image(path: Path, fmt: str = "JPEG"):
    img = Image.new("RGB", (100, 100), color="white")
    img.save(path, fmt)
    return path

def test_register_valid_jpeg(custom_root, monkeypatch):
    # Import after fixtures have patched constants
    from ml.scripts import register_custom_egg_images as reg

    src = _create_image(Path(os.getcwd()) / "temp.jpg")
    meta = reg.register_image(
        source=src,
        specimen_id="EGG001",
        view="top",
        lighting="natural",
        background="plain",
        photographer="Alice",
        custom_root=custom_root,
    )
    # Verify file copied
    assert (custom_root / "raw" / "EGG001" / f"{meta['capture_id']}.jpg").exists()
    # Verify side‑car JSON exists and content matches
    meta_path = custom_root / "metadata" / "EGG001" / f"{meta['capture_id']}.json"
    assert meta_path.exists()
    loaded = json.loads(meta_path.read_text())
    assert loaded["specimen_id"] == "EGG001"
    assert loaded["view"] == "top"
    # Verify manifest entry
    images_csv = custom_root / "manifests" / "images.csv"
    rows = list(csv.DictReader(images_csv.read_text().splitlines()))
    matching = [r for r in rows if r["image_id"] == meta["capture_id"]]
    assert len(matching) == 1
    # Cleanup source image
    src.unlink()

def test_duplicate_detection(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / "dup.png", fmt="PNG")
    # First registration should succeed
    reg.register_image(
        source=src,
        specimen_id="EGG002",
        view="side",
        custom_root=custom_root,
    )
    # Second registration of the same file should raise DuplicateImageError
    with pytest.raises(reg.DuplicateImageError):
        reg.register_image(
            source=src,
            specimen_id="EGG002",
            view="side",
            custom_root=custom_root,
        )
    src.unlink()

def test_unsupported_format(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    # Create a dummy .tiff file (unsupported)
    dummy = Path(os.getcwd()) / "bad.tiff"
    dummy.write_bytes(b"not an image")
    with pytest.raises(reg.RegistrationError) as exc:
        reg.register_image(
            source=dummy,
            specimen_id="EGG003",
            view="oblique",
            custom_root=custom_root,
        )
    assert "Unsupported file extension" in str(exc.value)
    dummy.unlink()

def test_corrupt_image(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    # Create a file with .jpg extension but invalid contents
    corrupt = Path(os.getcwd()) / "corrupt.jpg"
    corrupt.write_bytes(b"this is not a real jpeg file")
    with pytest.raises(reg.RegistrationError) as exc:
        reg.register_image(
            source=corrupt,
            specimen_id="EGG004",
            view="closeup",
            custom_root=custom_root,
        )
    assert "Corrupt or unreadable image" in str(exc.value)
    corrupt.unlink()

'''