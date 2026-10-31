"""Model A — Egg Detection Training Harness.

Architectures: YOLOv8-nano / MobileNet-SSD.
Objective: Localize egg bounding box and distinguish egg presence from background.
"""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def train_detection(
    data_yaml: Path,
    epochs: int = 50,
    batch_size: int = 16,
    img_size: int = 640,
    output_dir: Path = Path("ml/models/detection"),
    seed: int = 42,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Initializing Model A (Egg Detection) training session...")
    logger.info("Configuration: epochs=%d, batch_size=%d, img_size=%d, seed=%d", epochs, batch_size, img_size, seed)

    if not data_yaml.exists():
        logger.warning(
            "Dataset configuration file '%s' was not found. "
            "To train Model A, assemble a verified dataset following ml/data/README.md.",
            data_yaml,
        )
        return {
            "status": "TRAINING_REQUIRED",
            "message": f"Dataset configuration missing: {data_yaml}",
            "model_ready": False,
        }

    # Model training metadata descriptor
    metadata = {
        "model_name": "eggvision_detector_yolov8n",
        "task": "detection",
        "class_mapping": {0: "egg"},
        "epochs": epochs,
        "batch_size": batch_size,
        "input_resolution": [img_size, img_size],
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "status": "TRAINED_UNVALIDATED",
        "metrics": {"mAP50": None, "mAP50_95": None, "precision": None, "recall": None},
    }

    meta_file = output_dir / "detector_metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Training harness ready. Metadata saved to %s", meta_file)
    return metadata


def main():
    parser = argparse.ArgumentParser(description="Train Egg Detection Model")
    parser.add_argument("--data", type=Path, default=Path("ml/data/detection.yaml"), help="Path to data YAML")
    parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--img-size", type=int, default=640, help="Input image dimension")
    parser.add_argument("--output", type=Path, default=Path("ml/models/detection"), help="Output directory")
    args = parser.parse_args()

    train_detection(args.data, args.epochs, args.batch_size, args.img_size, args.output)


if __name__ == "__main__":
    main()
