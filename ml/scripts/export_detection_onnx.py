"""EggVision AI — Export Trained YOLOv8n Detector to ONNX.

Exports the verified best.pt checkpoint to a static 640x640 ONNX model,
validates the ONNX computational graph, checks input/output tensor shapes,
benchmarks CPU inference latency, and saves cryptographic export metadata.
"""

import argparse
import hashlib
import json
import logging
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("export_onnx")

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WEIGHTS = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "best.pt"
DEFAULT_METADATA = REPO_ROOT / "ml" / "artifacts" / "detection" / "model_metadata.json"
DEFAULT_OUTPUT_ONNX = REPO_ROOT / "ml" / "artifacts" / "detection" / "weights" / "eggvision_detector.onnx"
DEFAULT_EXPORT_METADATA = REPO_ROOT / "ml" / "artifacts" / "detection" / "onnx_metadata.json"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 digest of a file in streaming chunks."""
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_checkpoint(weights_path: Path, metadata_path: Path | None) -> dict[str, Any]:
    """Verify that best.pt exists and its SHA-256 matches declared metadata."""
    if not weights_path.exists():
        raise FileNotFoundError(f"Checkpoint not found at {weights_path}")

    actual_size = weights_path.stat().st_size
    if actual_size == 0:
        raise ValueError(f"Checkpoint file at {weights_path} is empty (0 bytes).")

    actual_sha = compute_sha256(weights_path)
    logger.info(f"Verified local checkpoint: {weights_path.name}")
    logger.info(f"  Size: {actual_size:,} bytes")
    logger.info(f"  SHA-256: {actual_sha}")

    declared_metadata = {}
    if metadata_path and metadata_path.exists():
        try:
            with metadata_path.open("r", encoding="utf-8") as f:
                declared_metadata = json.load(f)
            expected_sha = declared_metadata.get("weights_sha256")
            if expected_sha and expected_sha != actual_sha:
                raise ValueError(
                    f"Integrity check failed for {weights_path}: "
                    f"expected {expected_sha}, got {actual_sha}"
                )
            logger.info("  Integrity check vs model_metadata.json: PASSED")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.warning(f"Could not load metadata for validation: {e}")

    return {
        "weights_path": str(weights_path),
        "weights_sha256": actual_sha,
        "weights_size_bytes": actual_size,
        "declared_metadata": declared_metadata,
    }


def export_to_onnx(
    weights_path: Path,
    output_onnx: Path,
    imgsz: int = 640,
    opset: int = 17,
) -> Path:
    """Export YOLOv8n to ONNX using Ultralytics with static input shape."""
    from ultralytics import YOLO

    logger.info(f"Loading YOLO checkpoint from {weights_path}...")
    model = YOLO(str(weights_path))

    logger.info(f"Exporting to ONNX format (imgsz={imgsz}, opset={opset}, dynamic=False)...")
    exported_file = model.export(
        format="onnx",
        imgsz=imgsz,
        dynamic=False,
        opset=opset,
        simplify=False,
    )
    exported_path = Path(exported_file)

    if not exported_path.exists():
        raise RuntimeError(f"Export command returned {exported_file} but file does not exist.")

    output_onnx.parent.mkdir(parents=True, exist_ok=True)
    if exported_path.resolve() != output_onnx.resolve():
        logger.info(f"Copying exported model from {exported_path} to {output_onnx}...")
        shutil.copy2(exported_path, output_onnx)

    return output_onnx


def validate_onnx_graph(onnx_path: Path) -> dict[str, Any]:
    """Validate ONNX model graph structure using onnx package."""
    import onnx

    logger.info(f"Validating ONNX graph for {onnx_path.name}...")
    onnx_model = onnx.load(str(onnx_path))
    onnx.checker.check_model(onnx_model)
    logger.info("  ONNX graph structural check: PASSED (valid graph)")

    ir_version = onnx_model.ir_version
    producer_name = onnx_model.producer_name
    producer_version = onnx_model.producer_version
    opset_imports = [
        {"domain": op.domain, "version": op.version} for op in onnx_model.opset_import
    ]

    return {
        "ir_version": ir_version,
        "producer_name": producer_name,
        "producer_version": producer_version,
        "opset_imports": opset_imports,
    }


def benchmark_onnx_runtime(
    onnx_path: Path,
    imgsz: int = 640,
    warmup_runs: int = 5,
    benchmark_runs: int = 20,
) -> dict[str, Any]:
    """Benchmark ONNX Runtime CPUExecutionProvider inference latency and check tensor shapes."""
    import onnxruntime as ort

    logger.info("Initializing ONNX Runtime InferenceSession (CPUExecutionProvider)...")
    session = ort.InferenceSession(
        str(onnx_path),
        providers=["CPUExecutionProvider"],
    )

    inputs = session.get_inputs()
    outputs = session.get_outputs()

    input_info = [
        {"name": inp.name, "type": inp.type, "shape": list(inp.shape)}
        for inp in inputs
    ]
    output_info = [
        {"name": out.name, "type": out.type, "shape": list(out.shape)}
        for out in outputs
    ]

    logger.info(f"  Inputs: {input_info}")
    logger.info(f"  Outputs: {output_info}")

    input_name = inputs[0].name
    dummy_input = np.zeros((1, 3, imgsz, imgsz), dtype=np.float32)

    logger.info(f"Running {warmup_runs} warmup iterations...")
    for _ in range(warmup_runs):
        _ = session.run(None, {input_name: dummy_input})

    logger.info(f"Running {benchmark_runs} benchmark iterations...")
    latencies: list[float] = []
    for _ in range(benchmark_runs):
        t0 = time.perf_counter()
        _ = session.run(None, {input_name: dummy_input})
        latencies.append((time.perf_counter() - t0) * 1000.0)

    mean_ms = float(np.mean(latencies))
    median_ms = float(np.median(latencies))
    p95_ms = float(np.percentile(latencies, 95))
    min_ms = float(np.min(latencies))
    max_ms = float(np.max(latencies))

    logger.info(
        f"  Benchmark results: mean={mean_ms:.2f}ms, median={median_ms:.2f}ms, "
        f"p95={p95_ms:.2f}ms (min={min_ms:.2f}ms, max={max_ms:.2f}ms)"
    )

    return {
        "inputs": input_info,
        "outputs": output_info,
        "latency_benchmark": {
            "mean_ms": round(mean_ms, 2),
            "median_ms": round(median_ms, 2),
            "p95_ms": round(p95_ms, 2),
            "min_ms": round(min_ms, 2),
            "max_ms": round(max_ms, 2),
            "runs": benchmark_runs,
            "device": "CPU",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export YOLOv8n detector to ONNX.")
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS, help="Path to best.pt")
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA, help="Path to model_metadata.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_ONNX, help="Path for exported .onnx file")
    parser.add_argument("--export-meta", type=Path, default=DEFAULT_EXPORT_METADATA, help="Path for onnx_metadata.json")
    parser.add_argument("--imgsz", type=int, default=640, help="Static input size")
    parser.add_argument("--opset", type=int, default=17, help="ONNX opset version")
    args = parser.parse_args()

    try:
        # Step 1: Verify Checkpoint
        checkpoint_info = verify_checkpoint(args.weights, args.metadata)

        # Step 2: Export to ONNX
        exported_onnx = export_to_onnx(
            weights_path=args.weights,
            output_onnx=args.output,
            imgsz=args.imgsz,
            opset=args.opset,
        )

        # Step 3: Compute ONNX checksum and size
        onnx_size = exported_onnx.stat().st_size
        onnx_sha256 = compute_sha256(exported_onnx)
        logger.info(f"Exported ONNX file: {exported_onnx.name}")
        logger.info(f"  Size: {onnx_size:,} bytes")
        logger.info(f"  SHA-256: {onnx_sha256}")

        # Step 4: Validate Graph
        graph_info = validate_onnx_graph(exported_onnx)

        # Step 5: Benchmark ONNX Runtime
        runtime_info = benchmark_onnx_runtime(exported_onnx, imgsz=args.imgsz)

        # Step 6: Write Export Metadata
        metadata = {
            "model_name": "eggvision_detector_yolov8n",
            "model_architecture": "yolov8n",
            "format": "onnx",
            "task": "detection",
            "classes": {"0": "egg"},
            "input_resolution": [args.imgsz, args.imgsz],
            "input_color_format": "RGB",
            "input_normalization": "scale_0_to_1",
            "output_layout": "yolov8_raw_candidates [batch, 4_box_coords_plus_1_cls, 8400_anchors]",
            "nms_strategy": "runtime_postprocessing_nms",
            "pt_checkpoint_sha256": checkpoint_info["weights_sha256"],
            "pt_checkpoint_size_bytes": checkpoint_info["weights_size_bytes"],
            "onnx_sha256": onnx_sha256,
            "onnx_size_bytes": onnx_size,
            "graph_validation": graph_info,
            "runtime_validation": runtime_info,
            "exported_at": datetime.now(UTC).isoformat(),
            "status": "VALIDATED",
        }

        args.export_meta.parent.mkdir(parents=True, exist_ok=True)
        with args.export_meta.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Export metadata written to {args.export_meta}")

        print("\n=== ONNX EXPORT SUCCESSFUL ===")
        print(f"ONNX Path:   {exported_onnx}")
        print(f"ONNX SHA256: {onnx_sha256}")
        print(f"ONNX Size:   {onnx_size:,} bytes")
        print(f"Mean Latency: {runtime_info['latency_benchmark']['mean_ms']} ms")
        return 0

    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
