"""conftest.py – fixtures for EggVision test isolation.

Provides:
* `custom_root` – a temporary ``ml/data/custom_collection`` hierarchy.
* `patch_custom_root` – monkey‑patches all path constants used by
  ``ml.scripts.register_custom_egg_images`` so the registration code
  operates entirely inside the temporary directory.

The fixtures are autouse‑enabled for the registration tests and coexist
with any Phase‑2 snapshot‑protection fixtures that may exist elsewhere
in the test suite.
"""

import sys
from pathlib import Path
import pytest
import importlib

# Ensure the repository root is on PYTHONPATH for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Phase 3A fixtures – custom collection isolation
# ---------------------------------------------------------------------------

@pytest.fixture
def custom_root(tmp_path_factory):
    """Create an isolated ``custom_collection`` directory structure.

    Returns the temporary root path that mimics ``ml/data/custom_collection``.
    """
    root = tmp_path_factory.mktemp("custom_collection")
    # Expected sub‑folders
    (root / "raw").mkdir(parents=True, exist_ok=True)
    (root / "metadata").mkdir(parents=True, exist_ok=True)
    (root / "manifests").mkdir(parents=True, exist_ok=True)
    yield root
    # ``tmp_path_factory`` handles cleanup automatically.

@pytest.fixture(autouse=True)
def patch_custom_root(monkeypatch, custom_root):
    """Patch registration‑module constants to point at ``custom_root``.

    The target module is imported lazily; if it has already been loaded we
    reload it so that the patched globals take effect.
    """
    module_name = "ml.scripts.register_custom_egg_images"
    # Reload if already imported (helps interactive sessions)
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])
    module = importlib.import_module(module_name)
    # Patch all path constants used by the script
    monkeypatch.setattr(module, "DEFAULT_CUSTOM_ROOT", Path(custom_root), raising=False)
    monkeypatch.setattr(module, "RAW_ROOT", Path(custom_root) / "raw", raising=False)
    monkeypatch.setattr(module, "METADATA_ROOT", Path(custom_root) / "metadata", raising=False)
    monkeypatch.setattr(module, "MANIFESTS_ROOT", Path(custom_root) / "manifests", raising=False)
    monkeypatch.setattr(module, "IMAGES_CSV", Path(custom_root) / "manifests" / "images.csv", raising=False)
    monkeypatch.setattr(module, "SPECIMENS_CSV", Path(custom_root) / "manifests" / "specimens.csv", raising=False)
    yield
