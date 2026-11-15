"""EggVision AI — Model Manifest Validator & Schema Verification.

Implements strict validation of model manifests, cryptographic digests,
artifact dimensions, provenance metadata, and PyTorch/ONNX equivalence evidence.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("manifest_validator")

HEX_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_CLASS_MAPPING = {"0": "egg"}
EXPECTED_INPUT_RESOLUTION = [640, 640]
MIN_ALLOWED_OPSET = 11
MIN_ACCEPTABLE_IOU = 0.90


class ManifestValidationError(ValueError):
    """Raised when a model manifest is malformed, incomplete, or fails schema validation."""


def validate_sha256_format(digest: Any) -> str:
    """Validate that a digest is a non-empty string of exactly 64 lowercase hex characters."""
    if not isinstance(digest, str):
        raise ManifestValidationError(f"Expected SHA-256 digest string, got {type(digest).__name__}.")
    clean = digest.strip().lower()
    if not HEX_SHA256_PATTERN.match(clean):
        raise ManifestValidationError(
            f"Invalid SHA-256 format: '{digest}'. Must be exactly 64 hexadecimal characters."
        )
    return clean


def compute_file_sha256(filepath: Path) -> str:
    """Compute SHA-256 digest of a file in 64KB blocks."""
    if not filepath.exists():
        raise FileNotFoundError(f"File not found for SHA-256 computation: {filepath}")
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def validate_manifest_dict(manifest: Any) -> dict[str, Any]:
    """Strictly validate a parsed manifest dictionary against the Phase 3 schema requirements.

    Returns the validated manifest dictionary if successful, or raises ManifestValidationError.
    """
    if not isinstance(manifest, dict):
        raise ManifestValidationError(f"Manifest must be a JSON object, got {type(manifest).__name__}.")

    # 1. Schema version and model identity
    manifest_version = manifest.get("manifest_version")
    if not manifest_version or not isinstance(manifest_version, str):
        raise ManifestValidationError("Manifest missing mandatory 'manifest_version' string.")

    model_name = manifest.get("model_name")
    if not model_name or not isinstance(model_name, str):
        raise ManifestValidationError("Manifest missing mandatory 'model_name' string.")

    model_version = manifest.get("model_version")
    if not model_version or not isinstance(model_version, str):
        raise ManifestValidationError("Manifest missing mandatory 'model_version' string.")

    # 2. Task and class ontology
    task = manifest.get("task")
    if task != "detection":
        raise ManifestValidationError(f"Manifest task must be 'detection', got '{task}'.")

    classes = manifest.get("classes")
    if not isinstance(classes, dict) or classes.get("0") != "egg":
        raise ManifestValidationError(f"Manifest classes mapping must contain '0': 'egg', got {classes}.")

    # 3. Input specifications
    resolution = manifest.get("input_resolution")
    if resolution != EXPECTED_INPUT_RESOLUTION:
        raise ManifestValidationError(
            f"Manifest input_resolution must be {EXPECTED_INPUT_RESOLUTION}, got {resolution}."
        )

    # 4. ONNX artifact specification
    onnx_art = manifest.get("onnx_artifact")
    if not isinstance(onnx_art, dict):
        raise ManifestValidationError("Manifest missing mandatory 'onnx_artifact' section.")

    onnx_filename = onnx_art.get("filename")
    if not onnx_filename or not isinstance(onnx_filename, str) or not onnx_filename.endswith(".onnx"):
        raise ManifestValidationError(f"Invalid or missing ONNX filename: '{onnx_filename}'.")

    validate_sha256_format(onnx_art.get("sha256"))
    onnx_size = onnx_art.get("size_bytes")
    if not isinstance(onnx_size, int) or onnx_size <= 0:
        raise ManifestValidationError(f"Invalid ONNX declared size_bytes: {onnx_size}.")

    opset = onnx_art.get("opset")
    if not isinstance(opset, int) or opset < MIN_ALLOWED_OPSET:
        raise ManifestValidationError(f"ONNX opset must be an integer >= {MIN_ALLOWED_OPSET}, got {opset}.")

    # 5. Original checkpoint metadata
    orig_ckpt = manifest.get("original_checkpoint")
    if not isinstance(orig_ckpt, dict):
        raise ManifestValidationError("Manifest missing mandatory 'original_checkpoint' section.")

    arch = orig_ckpt.get("architecture")
    if arch != "yolov8n":
        raise ManifestValidationError(f"Model architecture must be 'yolov8n', got '{arch}'.")

    ckpt_sha = orig_ckpt.get("sha256")
    if ckpt_sha:
        validate_sha256_format(ckpt_sha)

    # 6. Provenance metadata
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("dataset_source"):
        raise ManifestValidationError("Manifest missing mandatory 'provenance.dataset_source' entry.")

    # 7. ONNX input/output specifications
    export_details = manifest.get("onnx_export_details")
    if not isinstance(export_details, dict):
        raise ManifestValidationError("Manifest missing mandatory 'onnx_export_details' section.")

    inputs = export_details.get("inputs")
    outputs = export_details.get("outputs")
    if not isinstance(inputs, list) or len(inputs) < 1 or not isinstance(outputs, list) or len(outputs) < 1:
        raise ManifestValidationError("Manifest 'onnx_export_details' must contain non-empty 'inputs' and 'outputs'.")

    # 8. Equivalence report verification
    equiv = manifest.get("onnx_equivalence")
    if not isinstance(equiv, dict):
        raise ManifestValidationError("Manifest missing mandatory 'onnx_equivalence' evaluation section.")

    mean_iou = equiv.get("mean_iou")
    if not isinstance(mean_iou, (int, float)) or mean_iou < MIN_ACCEPTABLE_IOU:
        raise ManifestValidationError(
            f"ONNX equivalence mean_iou ({mean_iou}) is below acceptable threshold ({MIN_ACCEPTABLE_IOU})."
        )

    return manifest


def validate_manifest_file(manifest_path: Path) -> dict[str, Any]:
    """Read a JSON manifest file from disk and validate it strictly."""
    if not manifest_path.exists():
        raise ManifestValidationError(f"Manifest file not found: {manifest_path}")

    try:
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ManifestValidationError(f"Manifest file is malformed JSON ({manifest_path}): {e}") from e
    except Exception as e:
        raise ManifestValidationError(f"Failed to read manifest ({manifest_path}): {e}") from e

    return validate_manifest_dict(data)


def verify_artifact_matches_manifest(artifact_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Verify that an actual artifact file matches the declared size and SHA-256 in the manifest."""
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact file not found: {artifact_path}")

    actual_size = artifact_path.stat().st_size
    if actual_size == 0:
        raise ManifestValidationError(f"Artifact file {artifact_path} is empty (0 bytes).")

    expected_size = manifest["onnx_artifact"]["size_bytes"]
    if actual_size != expected_size:
        raise ManifestValidationError(
            f"Artifact size mismatch for {artifact_path.name}: "
            f"expected {expected_size:,} bytes, actual is {actual_size:,} bytes."
        )

    expected_sha = manifest["onnx_artifact"]["sha256"]
    actual_sha = compute_file_sha256(artifact_path)
    if actual_sha != expected_sha:
        raise ManifestValidationError(
            f"Artifact SHA-256 mismatch for {artifact_path.name}: "
            f"expected {expected_sha}, got {actual_sha}."
        )

    return {
        "verified": True,
        "artifact_path": str(artifact_path),
        "sha256": actual_sha,
        "size_bytes": actual_size,
    }
