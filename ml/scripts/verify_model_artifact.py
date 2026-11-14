"""EggVision AI — Verify Model Artifact (Local or Remote S3).

Verifies byte size, cryptographic SHA-256 digest, manifest integrity,
and runtime execution readiness for a published or downloaded model artifact.
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

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("verify_artifact")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ONNX_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "eggvision_detector.onnx"
DEFAULT_MANIFEST_PATH = REPO_ROOT / "ml" / "artifacts" / "detection" / "manifest.json"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 digest in chunks."""
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_local_artifact(
    onnx_path: Path,
    manifest_path: Path | None = None,
    expected_sha: str | None = None,
) -> dict[str, Any]:
    """Verify local ONNX file against manifest and ONNX Runtime execution."""
    import onnxruntime as ort

    if not onnx_path.exists():
        raise FileNotFoundError(f"Model file not found at {onnx_path}")

    actual_size = onnx_path.stat().st_size
    actual_sha = compute_sha256(onnx_path)

    manifest_data: dict[str, Any] = {}
    if manifest_path and manifest_path.exists():
        with manifest_path.open("r", encoding="utf-8") as f:
            manifest_data = json.load(f)
        if not expected_sha:
            expected_sha = (
                manifest_data.get("onnx_artifact", {}).get("sha256")
                or manifest_data.get("onnx_sha256")
            )

    if expected_sha and actual_sha != expected_sha:
        raise ValueError(
            f"SHA-256 integrity mismatch: expected {expected_sha}, got {actual_sha}"
        )

    # Test ONNX Runtime session creation
    session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    dummy_input = np.zeros((1, 3, 640, 640), dtype=np.float32)
    output = session.run(None, {input_name: dummy_input})

    output_shape = list(output[0].shape)
    if len(output_shape) != 3 or output_shape[1] != 5:
        raise ValueError(f"Unexpected output shape from model: {output_shape}")

    logger.info(f"Artifact {onnx_path.name} verified successfully:")
    logger.info(f"  SHA-256: {actual_sha}")
    logger.info(f"  Size:    {actual_size:,} bytes")
    logger.info(f"  Output:  {output_shape}")

    return {
        "status": "VERIFIED",
        "file_path": str(onnx_path),
        "sha256": actual_sha,
        "size_bytes": actual_size,
        "output_shape": output_shape,
        "runtime_ready": True,
        "verified_at": datetime.now(UTC).isoformat(),
    }


def verify_s3_artifact(
    artifact_key: str,
    expected_sha: str,
    bucket: str | None = None,
) -> dict[str, Any]:
    """Download and verify remote S3 artifact without persisting locally."""
    import boto3
    from botocore.config import Config

    endpoint = os.getenv("MODEL_S3_ENDPOINT") or os.getenv("S3_ENDPOINT")
    bucket = bucket or os.getenv("MODEL_S3_BUCKET") or os.getenv("S3_BUCKET") or "eggvision-models"
    access_key = os.getenv("MODEL_S3_ACCESS_KEY") or os.getenv("S3_ACCESS_KEY")
    secret_key = os.getenv("MODEL_S3_SECRET_KEY") or os.getenv("S3_SECRET_KEY")
    region = os.getenv("MODEL_S3_REGION") or os.getenv("S3_REGION") or "us-east-1"

    if not (endpoint and access_key and secret_key):
        raise ValueError("S3 credentials not configured for remote verification.")

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4"),
    )

    with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        logger.info(f"Downloading s3://{bucket}/{artifact_key} for verification...")
        client.download_file(bucket, artifact_key, str(tmp_path))
        res = verify_local_artifact(tmp_path, expected_sha=expected_sha)
        res["s3_bucket"] = bucket
        res["s3_key"] = artifact_key
        return res
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify local or remote model artifact.")
    parser.add_argument("--onnx-path", type=Path, default=DEFAULT_ONNX_PATH)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--expected-sha", type=str, default=None)
    parser.add_argument("--s3-key", type=str, default=None)
    parser.add_argument("--s3-bucket", type=str, default=None)
    args = parser.parse_args()

    try:
        if args.s3_key:
            if not args.expected_sha:
                logger.error("--expected-sha is required when verifying remote S3 artifact.")
                return 1
            result = verify_s3_artifact(
                artifact_key=args.s3_key,
                expected_sha=args.expected_sha,
                bucket=args.s3_bucket,
            )
        else:
            result = verify_local_artifact(
                onnx_path=args.onnx_path,
                manifest_path=args.manifest,
                expected_sha=args.expected_sha,
            )

        print("\n=== ARTIFACT VERIFICATION SUCCESSFUL ===")
        print(f"Status:   {result['status']}")
        print(f"SHA-256:  {result['sha256']}")
        print(f"Size:     {result['size_bytes']:,} bytes")
        print(f"Runtime:  Ready (output shape: {result['output_shape']})")
        return 0

    except Exception as e:
        logger.error(f"Artifact verification failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
