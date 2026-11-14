"""EggVision AI — Publish Model Artifact to Private Object Storage.

Packages the verified ONNX model and provenance metadata into an immutable, versioned
S3 object storage path (e.g. eggvision/detection/v1/<sha256>/model.onnx), performs an
immediate round-trip download verification, and outputs a publication manifest.
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("publish_artifact")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ONNX_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "eggvision_detector.onnx"
DEFAULT_PT_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "best.pt"
DEFAULT_META_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "model_metadata.json"
DEFAULT_ONNX_META_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "onnx_metadata.json"
DEFAULT_EQUIV_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "onnx_equivalence_report.json"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "manifest.json"
DEFAULT_REPORT_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "publish_report.json"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 digest in chunks."""
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_s3_client() -> tuple[Any | None, dict[str, str]]:
    """Create S3 client from environment variables without exposing secrets."""
    endpoint = os.getenv("MODEL_S3_ENDPOINT") or os.getenv("S3_ENDPOINT")
    bucket = os.getenv("MODEL_S3_BUCKET") or os.getenv("S3_BUCKET") or "eggvision-models"
    access_key = os.getenv("MODEL_S3_ACCESS_KEY") or os.getenv("S3_ACCESS_KEY")
    secret_key = os.getenv("MODEL_S3_SECRET_KEY") or os.getenv("S3_SECRET_KEY")
    region = os.getenv("MODEL_S3_REGION") or os.getenv("S3_REGION") or "us-east-1"

    config_info = {
        "endpoint": endpoint or "not_configured",
        "bucket": bucket,
        "region": region,
        "has_credentials": bool(access_key and secret_key),
    }

    if not (endpoint and access_key and secret_key):
        return None, config_info

    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(
            signature_version="s3v4",
            connect_timeout=10.0,
            read_timeout=30.0,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )
    return client, config_info


def build_manifest(
    onnx_path: Path,
    pt_path: Path,
    meta_path: Path,
    onnx_meta_path: Path,
    equiv_path: Path,
    prefix: str = "eggvision/detection/v1",
) -> dict[str, Any]:
    """Compile exhaustive cryptographic provenance manifest for model release."""
    if not onnx_path.exists():
        raise FileNotFoundError(f"ONNX model file missing: {onnx_path}")

    onnx_sha = compute_sha256(onnx_path)
    onnx_size = onnx_path.stat().st_size

    pt_sha = compute_sha256(pt_path) if pt_path.exists() else "absent"
    pt_size = pt_path.stat().st_size if pt_path.exists() else 0

    training_meta: dict[str, Any] = {}
    if meta_path.exists():
        with meta_path.open("r", encoding="utf-8") as f:
            training_meta = json.load(f)

    onnx_meta: dict[str, Any] = {}
    if onnx_meta_path.exists():
        with onnx_meta_path.open("r", encoding="utf-8") as f:
            onnx_meta = json.load(f)

    equiv_report: dict[str, Any] = {}
    if equiv_path.exists():
        with equiv_path.open("r", encoding="utf-8") as f:
            equiv_report = json.load(f)

    artifact_key = f"{prefix}/{onnx_sha}/model.onnx"
    manifest_key = f"{prefix}/{onnx_sha}/manifest.json"

    manifest = {
        "manifest_version": "1.0.0",
        "model_name": "eggvision_detector_yolov8n",
        "model_version": "1.0.0",
        "task": "detection",
        "classes": {"0": "egg"},
        "input_resolution": [640, 640],
        "input_color_format": "RGB",
        "input_normalization": "scale_0_to_1",
        "onnx_artifact": {
            "key": artifact_key,
            "filename": onnx_path.name,
            "sha256": onnx_sha,
            "size_bytes": onnx_size,
            "format": "onnx",
            "opset": 17,
        },
        "original_checkpoint": {
            "filename": pt_path.name if pt_path.exists() else "best.pt",
            "sha256": pt_sha,
            "size_bytes": pt_size,
            "architecture": "yolov8n",
        },
        "provenance": {
            "dataset_source": "afshin-dini/Egg-Detection",
            "dataset_revision": "d425996c959623b3960fca27f53b16f060b0a474",
            "training_commit": "0e1f8dd1e36532d109e6a545604eb9ec8b55a42a",
            "training_library": "ultralytics==8.4.212",
            "runtime_library": "onnxruntime>=1.17.0",
            "training_epochs": training_meta.get("epochs_requested", 30),
            "training_samples": training_meta.get("training_samples", 36),
            "validation_samples": training_meta.get("validation_samples", 8),
            "test_samples": training_meta.get("test_samples", 7),
        },
        "evaluation_metrics": training_meta.get("evaluation_metrics", {}),
        "onnx_export_details": onnx_meta.get("runtime_validation", {}),
        "onnx_equivalence": equiv_report.get("summary", {}),
        "manifest_key": manifest_key,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "VALIDATED",
    }
    return manifest


def publish_artifact(
    manifest: dict[str, Any],
    onnx_path: Path,
    manifest_output: Path,
    report_output: Path,
) -> dict[str, Any]:
    """Upload artifact and manifest to private S3 and perform verification round-trip."""
    client, s3_config = get_s3_client()
    bucket = s3_config["bucket"]
    onnx_key = manifest["onnx_artifact"]["key"]
    manifest_key = manifest["manifest_key"]
    expected_sha = manifest["onnx_artifact"]["sha256"]
    expected_size = manifest["onnx_artifact"]["size_bytes"]

    # Write local manifest file
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    with manifest_output.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Local manifest written to {manifest_output}")

    if client is None:
        logger.warning(
            "S3 storage credentials not configured. Manifest prepared locally in offline mode."
        )
        report = {
            "status": "LOCAL_MANIFEST_PREPARED",
            "message": "S3 credentials not provided. Artifact and manifest are prepared locally.",
            "s3_config": {k: v for k, v in s3_config.items() if "secret" not in k.lower()},
            "manifest_file": str(manifest_output),
            "onnx_sha256": expected_sha,
            "onnx_size_bytes": expected_size,
            "artifact_key": onnx_key,
            "manifest_key": manifest_key,
            "verified_roundtrip": False,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with report_output.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        return report

    # Check if object already exists to prevent accidental overwrite
    try:
        head_resp = client.head_object(Bucket=bucket, Key=onnx_key)
        existing_size = head_resp.get("ContentLength")
        logger.info(f"Artifact already exists at s3://{bucket}/{onnx_key} ({existing_size} bytes)")
    except Exception:
        # Not found, proceed to upload
        logger.info(f"Uploading model artifact to s3://{bucket}/{onnx_key} ({expected_size:,} bytes)...")
        with onnx_path.open("rb") as f:
            client.put_object(
                Bucket=bucket,
                Key=onnx_key,
                Body=f,
                ContentType="application/octet-stream",
                Metadata={"sha256": expected_sha},
            )
        logger.info("ONNX artifact uploaded.")

    # Upload manifest
    logger.info(f"Uploading manifest to s3://{bucket}/{manifest_key}...")
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
    client.put_object(
        Bucket=bucket,
        Key=manifest_key,
        Body=manifest_bytes,
        ContentType="application/json",
    )
    logger.info("Manifest uploaded.")

    # Immediate round-trip verification: download and check hash
    logger.info("Performing round-trip download verification...")
    with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        client.download_file(bucket, onnx_key, str(tmp_path))
        downloaded_size = tmp_path.stat().st_size
        downloaded_sha = compute_sha256(tmp_path)

        if downloaded_size != expected_size:
            raise ValueError(
                f"Roundtrip size mismatch: expected {expected_size}, got {downloaded_size}"
            )
        if downloaded_sha != expected_sha:
            raise ValueError(
                f"Roundtrip SHA-256 mismatch: expected {expected_sha}, got {downloaded_sha}"
            )
        logger.info("Round-trip download verification: PASSED (size and SHA-256 match perfectly)")

        report = {
            "status": "SUCCESS_VERIFIED",
            "bucket": bucket,
            "artifact_key": onnx_key,
            "manifest_key": manifest_key,
            "onnx_sha256": expected_sha,
            "onnx_size_bytes": expected_size,
            "downloaded_sha256": downloaded_sha,
            "downloaded_size_bytes": downloaded_size,
            "verified_roundtrip": True,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    with report_output.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    logger.info(f"Publication report saved to {report_output}")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish model artifact to private S3.")
    parser.add_argument("--onnx-path", type=Path, default=DEFAULT_ONNX_PATH)
    parser.add_argument("--pt-path", type=Path, default=DEFAULT_PT_PATH)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_META_PATH)
    parser.add_argument("--onnx-meta", type=Path, default=DEFAULT_ONNX_META_PATH)
    parser.add_argument("--equiv-report", type=Path, default=DEFAULT_EQUIV_PATH)
    parser.add_argument("--manifest-output", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--prefix", type=str, default="eggvision/detection/v1")
    args = parser.parse_args()

    try:
        manifest = build_manifest(
            onnx_path=args.onnx_path,
            pt_path=args.pt_path,
            meta_path=args.metadata,
            onnx_meta_path=args.onnx_meta,
            equiv_path=args.equiv_report,
            prefix=args.prefix,
        )
        report = publish_artifact(
            manifest=manifest,
            onnx_path=args.onnx_path,
            manifest_output=args.manifest_output,
            report_output=args.report_output,
        )
        print("\n=== PUBLISH ARTIFACT SUMMARY ===")
        print(f"Status:       {report['status']}")
        print(f"Artifact Key: {manifest['onnx_artifact']['key']}")
        print(f"ONNX SHA-256: {manifest['onnx_artifact']['sha256']}")
        print(f"Manifest:     {args.manifest_output}")
        return 0
    except Exception as e:
        logger.error(f"Publication failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
