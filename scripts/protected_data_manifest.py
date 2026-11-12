"""Create and compare integrity manifests for protected EggVision data.

The tool deliberately writes its JSON output outside the protected paths.  It
is suitable for pre/post verification snapshots; it does not mutate or repair
the data it inventories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROTECTED_PATHS = (
    "ml/data/raw",
    "ml/data/custom",
    "ml/data/custom_collection",
    "ml/data/inspection_report.csv",
    "ml/data/openimages_egg_detection_boxes.csv",
    "ml/data/egg_inspection_contact_sheet.jpg",
    "ml/data/fiftyone_cache",
    "ml/models",
    "mlruns",
    "mlartifacts",
    "uploads",
)


@dataclass(frozen=True)
class FileRecord:
    """Stable representation of one regular file."""

    sha256: str
    size: int


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of *path* without loading it all into RAM."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(path: Path) -> Iterable[Path]:
    if path.is_file():
        yield path
    elif path.is_dir():
        yield from (candidate for candidate in sorted(path.rglob("*")) if candidate.is_file())


def create_manifest(
    repository_root: Path = REPOSITORY_ROOT,
    protected_paths: Iterable[str] = DEFAULT_PROTECTED_PATHS,
) -> dict[str, object]:
    """Return an integrity manifest for configured paths below *repository_root*."""
    root = repository_root.resolve()
    records: dict[str, FileRecord] = {}
    paths: dict[str, str] = {}

    for configured_path in protected_paths:
        resolved = (root / configured_path).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise ValueError(f"Protected path escapes repository root: {configured_path}") from error

        paths[configured_path] = "present" if resolved.exists() else "missing"
        for file_path in _iter_files(resolved):
            relative = file_path.relative_to(root).as_posix()
            records[relative] = FileRecord(
                sha256=sha256_file(file_path), size=file_path.stat().st_size
            )

    return {
        "format_version": 1,
        "repository_root": str(root),
        "protected_paths": paths,
        "files": {path: asdict(record) for path, record in sorted(records.items())},
    }


def compare_manifests(before: dict[str, object], after: dict[str, object]) -> dict[str, list[str]]:
    """Report additions, removals and changes using the union of both manifests."""
    before_files = before.get("files", {})
    after_files = after.get("files", {})
    if not isinstance(before_files, dict) or not isinstance(after_files, dict):
        raise TypeError("Manifest is missing a files mapping")

    added = sorted(set(after_files) - set(before_files))
    removed = sorted(set(before_files) - set(after_files))
    changed = sorted(
        path
        for path in set(before_files).intersection(after_files)
        if before_files[path] != after_files[path]
    )
    return {"added": added, "removed": removed, "changed": changed}


def _load_manifest(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as file:
        loaded = json.load(file)
    if not isinstance(loaded, dict):
        raise TypeError(f"Manifest must be a JSON object: {path}")
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write a fresh manifest to this JSON file.")
    parser.add_argument("--compare", type=Path, help="Compare this manifest against --output.")
    parser.add_argument("--repository-root", type=Path, default=REPOSITORY_ROOT)
    parser.add_argument(
        "--protected-path",
        action="append",
        dest="protected_paths",
        help="Relative protected path; repeat to replace the default set.",
    )
    args = parser.parse_args()

    if not args.output:
        parser.error("--output is required")
    if args.compare and not args.compare.exists():
        parser.error(f"Comparison manifest does not exist: {args.compare}")

    manifest = create_manifest(
        repository_root=args.repository_root,
        protected_paths=args.protected_paths or DEFAULT_PROTECTED_PATHS,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote manifest with {len(manifest['files'])} files: {args.output}")

    if args.compare:
        changes = compare_manifests(_load_manifest(args.compare), manifest)
        print(json.dumps(changes, sort_keys=True))
        return 1 if any(changes.values()) else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
