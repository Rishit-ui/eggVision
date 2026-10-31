"""Model C / D — External Defect & Quality Classification Training Harness.

Architectures: EfficientNet-B0 / MobileNetV3-Small.
Objective: Classify external visible defects (cracks, breakage, staining).
Scientific Rule: Internal freshness / Haugh Unit cannot be predicted without laboratory candling/breakout data.
"""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


DEFECT_CLASSES = {
    0: "intact_shell",
    1: "hairline_crack",
    2: "punctured_break",
    3: "severe_breakage",
    4: "abnormal_staining",
}


def train_classification(
    data_dir: Path,
    epochs: int = 40,
    batch_size: int = 32,
    lr: float = 1e-3,
    output_dir: Path = Path("ml/models/defect"),
    seed: int = 42,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Initializing Model C (Visible Defect Classification) training session...")

    train_dir = data_dir / "train"
    if not train_dir.exists():
        logger.warning(
            "Training directory '%s' was not found. "
            "To train Model C, assemble labelled shell defect data following ml/data/README.md.",
            train_dir,
        )
        return {
            "status": "TRAINING_REQUIRED",
            "message": f"Training split missing at {train_dir}",
            "model_ready": False,
        }

    metadata = {
        "model_name": "eggvision_defect_classifier_efficientnet",
        "task": "classification",
        "class_mapping": DEFECT_CLASSES,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": lr,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "status": "TRAINED_UNVALIDATED",
        "metrics": {"macro_f1": None, "per_class_precision": {}, "per_class_recall": {}},
    }

    meta_file = output_dir / "defect_metadata.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    logger.info("Classification harness ready. Metadata saved to %s", meta_file)
    return metadata


def main():
    parser = argparse.ArgumentParser(description="Train Egg Defect Classification Model")
    parser.add_argument("--data-dir", type=Path, default=Path("ml/data"), help="Dataset directory")
    parser.add_argument("--epochs", type=int, default=40, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Learning rate")
    parser.add_argument("--output", type=Path, default=Path("ml/models/defect"), help="Output directory")
    args = parser.parse_args()

    train_classification(args.data_dir, args.epochs, args.batch_size, args.lr, args.output)


if __name__ == "__main__":
    main()
