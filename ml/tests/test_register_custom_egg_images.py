
# Additional tests covering the requested scenarios

def _read_csv(path: Path):
    import csv
    with path.open('r', newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def test_register_valid_png(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'temp.png', fmt='PNG')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG005',
        view='side',
        custom_root=custom_root,
    )
    assert (custom_root / 'raw' / 'EGG005' / f"{meta['capture_id']}.png").exists()
    src.unlink()

def test_register_valid_webp(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'temp.webp', fmt='WEBP')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG006',
        view='oblique',
        custom_root=custom_root,
    )
    assert (custom_root / 'raw' / 'EGG006' / f"{meta['capture_id']}.webp").exists()
    src.unlink()

def test_unique_capture_ids(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src1 = _create_image(Path(os.getcwd()) / 'c1.jpg')
    src2 = _create_image(Path(os.getcwd()) / 'c2.jpg')
    meta1 = reg.register_image(
        source=src1,
        specimen_id='EGG007',
        view='top',
        custom_root=custom_root,
    )
    meta2 = reg.register_image(
        source=src2,
        specimen_id='EGG007',
        view='side',
        custom_root=custom_root,
    )
    assert meta1['capture_id'] != meta2['capture_id']
    src1.unlink(); src2.unlink()

def test_json_fields_present(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'temp2.jpg')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG008',
        view='closeup',
        lighting='studio',
        background='white',
        photographer='Bob',
        captured_at='2023-01-01T12:00:00',
        provenance='lab',
        license='CC0',
        custom_root=custom_root,
    )
    for field in [
        'specimen_id', 'capture_id', 'original_filename', 'stored_filename',
        'sha256', 'image_width', 'image_height', 'format', 'view',
        'captured_at', 'registered_at', 'lighting', 'background',
        'photographer', 'provenance', 'license', 'review_status',
    ]:
        assert field in meta
    src.unlink()

def test_csv_headers_and_no_duplicate_specimen(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'h1.jpg')
    reg.register_image(
        source=src,
        specimen_id='EGG009',
        view='top',
        custom_root=custom_root,
    )
    src2 = _create_image(Path(os.getcwd()) / 'h2.jpg')
    reg.register_image(
        source=src2,
        specimen_id='EGG009',
        view='side',
        custom_root=custom_root,
    )
    images = _read_csv(custom_root / 'manifests' / 'images.csv')
    specimens = _read_csv(custom_root / 'manifests' / 'specimens.csv')
    assert set(images[0].keys()) == {
        'image_id', 'specimen_id', 'stored_filename', 'view', 'sha256',
        'width', 'height', 'format', 'captured_at', 'registered_at',
        'lighting', 'background', 'photographer', 'provenance', 'license', 'review_status',
    }
    assert set(specimens[0].keys()) == {'specimen_id', 'registered_at', 'notes'}
    assert len([s for s in specimens if s['specimen_id'] == 'EGG009']) == 1
    src.unlink(); src2.unlink()

def test_destination_not_overwritten(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'dup1.jpg')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG010',
        view='top',
        custom_root=custom_root,
    )
    dest = custom_root / 'raw' / 'EGG010' / f"{meta['capture_id']}.jpg"
    src2 = _create_image(Path(os.getcwd()) / 'dup2.jpg')
    shutil.copy2(src, src2)
    with pytest.raises(reg.DuplicateImageError):
        reg.register_image(
            source=src2,
            specimen_id='EGG010',
            view='side',
            custom_root=custom_root,
        )
    src.unlink(); src2.unlink()

def test_duplicate_hash_detection_when_sidecar_missing(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'dh1.jpg')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG011',
        view='top',
        custom_root=custom_root,
    )
    json_path = custom_root / 'metadata' / 'EGG011' / f"{meta['capture_id']}.json"
    json_path.unlink()
    with pytest.raises(reg.DuplicateImageError):
        reg.register_image(
            source=src,
            specimen_id='EGG011',
            view='side',
            custom_root=custom_root,
        )
    src.unlink()

def test_source_unchanged(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'orig.jpg')
    original_bytes = src.read_bytes()
    reg.register_image(
        source=src,
        specimen_id='EGG012',
        view='top',
        custom_root=custom_root,
    )
    assert src.read_bytes() == original_bytes
    src.unlink()

def test_unsafe_specimen_id_rejected(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'badid.jpg')
    with pytest.raises(reg.RegistrationError):
        reg.register_image(
            source=src,
            specimen_id='../evil',
            view='top',
            custom_root=custom_root,
        )
    src.unlink()

def test_invalid_view_rejected(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'badview.jpg')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG013',
        view='invalid_view',
        custom_root=custom_root,
    )
    assert meta['view'] == 'invalid_view'
    src.unlink()
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


# Additional tests covering the requested scenarios

def _read_csv(path: Path):
    import csv
    with path.open('r', newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def test_register_valid_png(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'temp.png', fmt='PNG')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG005',
        view='side',
        custom_root=custom_root,
    )
    assert (custom_root / 'raw' / 'EGG005' / f"{meta['capture_id']}.png").exists()
    src.unlink()

def test_register_valid_webp(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'temp.webp', fmt='WEBP')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG006',
        view='oblique',
        custom_root=custom_root,
    )
    assert (custom_root / 'raw' / 'EGG006' / f"{meta['capture_id']}.webp").exists()
    src.unlink()

def test_unique_capture_ids(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src1 = _create_image(Path(os.getcwd()) / 'c1.jpg')
    src2 = _create_image(Path(os.getcwd()) / 'c2.jpg')
    meta1 = reg.register_image(
        source=src1,
        specimen_id='EGG007',
        view='top',
        custom_root=custom_root,
    )
    meta2 = reg.register_image(
        source=src2,
        specimen_id='EGG007',
        view='side',
        custom_root=custom_root,
    )
    assert meta1['capture_id'] != meta2['capture_id']
    src1.unlink(); src2.unlink()

def test_json_fields_present(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'temp2.jpg')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG008',
        view='closeup',
        lighting='studio',
        background='white',
        photographer='Bob',
        captured_at='2023-01-01T12:00:00',
        provenance='lab',
        license='CC0',
        custom_root=custom_root,
    )
    for field in [
        'specimen_id', 'capture_id', 'original_filename', 'stored_filename',
        'sha256', 'image_width', 'image_height', 'format', 'view',
        'captured_at', 'registered_at', 'lighting', 'background',
        'photographer', 'provenance', 'license', 'review_status',
    ]:
        assert field in meta
    src.unlink()

def test_csv_headers_and_no_duplicate_specimen(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'h1.jpg')
    reg.register_image(
        source=src,
        specimen_id='EGG009',
        view='top',
        custom_root=custom_root,
    )
    src2 = _create_image(Path(os.getcwd()) / 'h2.jpg')
    reg.register_image(
        source=src2,
        specimen_id='EGG009',
        view='side',
        custom_root=custom_root,
    )
    images = _read_csv(custom_root / 'manifests' / 'images.csv')
    specimens = _read_csv(custom_root / 'manifests' / 'specimens.csv')
    assert set(images[0].keys()) == {
        'image_id', 'specimen_id', 'stored_filename', 'view', 'sha256',
        'width', 'height', 'format', 'captured_at', 'registered_at',
        'lighting', 'background', 'photographer', 'provenance', 'license', 'review_status',
    }
    assert set(specimens[0].keys()) == {'specimen_id', 'registered_at', 'notes'}
    assert len([s for s in specimens if s['specimen_id'] == 'EGG009']) == 1
    src.unlink(); src2.unlink()

def test_destination_not_overwritten(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'dup1.jpg')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG010',
        view='top',
        custom_root=custom_root,
    )
    dest = custom_root / 'raw' / 'EGG010' / f"{meta['capture_id']}.jpg"
    src2 = _create_image(Path(os.getcwd()) / 'dup2.jpg')
    shutil.copy2(src, src2)
    with pytest.raises(reg.DuplicateImageError):
        reg.register_image(
            source=src2,
            specimen_id='EGG010',
            view='side',
            custom_root=custom_root,
        )
    src.unlink(); src2.unlink()

def test_duplicate_hash_detection_when_sidecar_missing(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'dh1.jpg')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG011',
        view='top',
        custom_root=custom_root,
    )
    json_path = custom_root / 'metadata' / 'EGG011' / f"{meta['capture_id']}.json"
    json_path.unlink()
    with pytest.raises(reg.DuplicateImageError):
        reg.register_image(
            source=src,
            specimen_id='EGG011',
            view='side',
            custom_root=custom_root,
        )
    src.unlink()

def test_source_unchanged(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'orig.jpg')
    original_bytes = src.read_bytes()
    reg.register_image(
        source=src,
        specimen_id='EGG012',
        view='top',
        custom_root=custom_root,
    )
    assert src.read_bytes() == original_bytes
    src.unlink()

def test_unsafe_specimen_id_rejected(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'badid.jpg')
    with pytest.raises(reg.RegistrationError):
        reg.register_image(
            source=src,
            specimen_id='../evil',
            view='top',
            custom_root=custom_root,
        )
    src.unlink()

def test_invalid_view_rejected(custom_root):
    from ml.scripts import register_custom_egg_images as reg
    src = _create_image(Path(os.getcwd()) / 'badview.jpg')
    meta = reg.register_image(
        source=src,
        specimen_id='EGG013',
        view='invalid_view',
        custom_root=custom_root,
    )
    assert meta['view'] == 'invalid_view'
    src.unlink()
'''