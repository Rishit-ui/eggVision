"""Regression tests for protected-data inventory and union-based comparison."""

from __future__ import annotations

from pathlib import Path

from scripts.protected_data_manifest import compare_manifests, create_manifest


def test_manifest_comparison_detects_add_modify_and_delete(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    protected.mkdir()
    retained = protected / "retained.txt"
    removed = protected / "removed.txt"
    retained.write_text("before", encoding="utf-8")
    removed.write_text("delete me", encoding="utf-8")

    before = create_manifest(tmp_path, ("protected",))

    retained.write_text("after", encoding="utf-8")
    removed.unlink()
    (protected / "added.txt").write_text("new", encoding="utf-8")

    after = create_manifest(tmp_path, ("protected",))
    assert compare_manifests(before, after) == {
        "added": ["protected/added.txt"],
        "removed": ["protected/removed.txt"],
        "changed": ["protected/retained.txt"],
    }


def test_manifest_records_missing_protected_path_without_creating_it(tmp_path: Path) -> None:
    manifest = create_manifest(tmp_path, ("does-not-exist",))
    assert manifest["protected_paths"] == {"does-not-exist": "missing"}
    assert manifest["files"] == {}
    assert not (tmp_path / "does-not-exist").exists()
