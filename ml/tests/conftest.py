'''conftest.py

import shutil
import sys
from pathlib import Path
import pytest

# Ensure the repository root is on PYTHONPATH for imports
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

@pytest.fixture
def custom_root(tmp_path_factory):
    """Create an isolated custom_collection directory structure for tests.
    Returns the Path to the root (equivalent to ml/data/custom_collection).
    """
    root = tmp_path_factory.mktemp("custom_collection")
    # create expected subfolders
    (root / "raw").mkdir(parents=True, exist_ok=True)
    (root / "metadata").mkdir(parents=True, exist_ok=True)
    (root / "manifests").mkdir(parents=True, exist_ok=True)
    yield root
    # Cleanup is automatic via tmp_path_factory

@pytest.fixture(autouse=True)
def patch_custom_root(monkeypatch, custom_root):
    """Monkey‑patch the registration module constants to point at the temporary root.
    The module is imported lazily inside each test, so we patch the attribute before import.
    """
    import importlib
    module_name = "ml.scripts.register_custom_egg_images"
    # If the module is already loaded, reload after patching globals that affect defaults
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])
    # Patch the DEFAULT_CUSTOM_ROOT constant after import
    module = importlib.import_module(module_name)
    monkeypatch.setattr(module, "DEFAULT_CUSTOM_ROOT", Path(custom_root), raising=False)
    # Also ensure the derived paths inside the module reflect the new root
    monkeypatch.setattr(module, "RAW_ROOT", Path(custom_root) / "raw", raising=False)
    monkeypatch.setattr(module, "METADATA_ROOT", Path(custom_root) / "metadata", raising=False)
    monkeypatch.setattr(module, "MANIFESTS_ROOT", Path(custom_root) / "manifests", raising=False)
    monkeypatch.setattr(module, "IMAGES_CSV", Path(custom_root) / "manifests" / "images.csv", raising=False)
    monkeypatch.setattr(module, "SPECIMENS_CSV", Path(custom_root) / "manifests" / "specimens.csv", raising=False)
    yield
