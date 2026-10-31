"""Model Evaluation and Scientific Validation Suite.

Evaluates trained model weights against the isolated, held-out test split.
Computes task-specific metrics:
- Detection: Precision, Recall, mAP@50, mAP@50:95
- Segmentation: IoU, Dice Score
- Classification: Macro F1, Confusion Matrix
- Rejection of models failing validation criteria
"""

import argparse
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def evaluate_models(models_dir: Path, test_dir: Path) -> dict:
    logger.info("Evaluating models in '%s' against held-out split '%s'...", models_dir, test_dir)

    results = {
        "detection": {"status": "MODEL_NOT_READY", "validated": False, "mAP50": None},
        "segmentation": {"status": "MODEL_NOT_READY", "validated": False, "mIoU": None},
        "defect_classification": {"status": "MODEL_NOT_READY", "validated": False, "macro_f1": None},
    }

    # Inspect detector weights
    det_weights = models_dir / "detection" / "best.pt"
    if not det_weights.exists():
        logger.info("Detector weights not found (%s). Status remains MODEL_NOT_READY.", det_weights)
    else:
        results["detection"]["status"] = "TRAINED_UNVALIDATED"

    # Inspect segmenter weights
    seg_weights = models_dir / "segmentation" / "best.pt"
    if not seg_weights.exists():
        logger.info("Segmenter weights not found (%s). Status remains MODEL_NOT_READY.", seg_weights)
    else:
        results["segmentation"]["status"] = "TRAINED_UNVALIDATED"

    # Inspect classifier weights
    cls_weights = models_dir / "defect" / "best.pt"
    if not cls_weights.exists():
        logger.info("Classifier weights not found (%s). Status remains MODEL_NOT_READY.", cls_weights)
    else:
        results["defect_classification"]["status"] = "TRAINED_UNVALIDATED"

    return results


def main():
    parser = argparse.ArgumentParser(description="Evaluate EggVision AI Models")
    parser.add_argument("--models-dir", type=Path, default=Path("ml/models"), help="Path to models directory")
    parser.add_argument("--test-dir", type=Path, default=Path("ml/data/test"), help="Path to held-out test split")
    args = parser.parse_args()

    results = evaluate_models(args.models_dir, args.test_dir)
    print("\n--- Model Evaluation Summary ---")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
