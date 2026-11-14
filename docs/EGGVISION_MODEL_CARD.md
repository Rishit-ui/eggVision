# EggVision AI — Formal Machine Learning Model Card
**Document Version:** 1.1.0  
**Format:** Mitchell et al. (2019) Model Cards for Model Reporting  
**Active Registered Model:** `eggvision_detector_yolov8n`  
**Current Version:** `1.0.0`  
**Deployment Status:** `VALIDATED` (Model A — Visible Egg Shell Detector Active)

---

## 1. Model Details

- **Developing Organization:** EggVision AI Research Project.
- **Model Name:** `eggvision_detector_yolov8n`
- **Architecture:** Ultralytics YOLOv8n (Nano detection backbone: 73 layers, 3,132,707 parameters, 8.6 GFLOPs).
- **Task:** Visible egg presence screening and bounding-box localization.
- **Trained Artifact:** `ml/artifacts/detection/weights/best.pt` (6,492,138 bytes).
- **Artifact SHA-256:** `dee854f1b36b16d2076c66a372c00517b961750d90e8115ac726bab7d0055732`.
- **License:** MIT License.
- **Contact:** Research IT Supervisor (`admin@eggvision.org`).

---

## 2. Intended Use & Scope

### 2.1 Primary Intended Uses
- Real-time optical screening to detect whether one or more eggs are present in a capture frame.
- Precise bounding-box localization ($[x_1, y_1, x_2, y_2]$) of visible eggs against diverse backgrounds.
- Rejection of non-egg objects or empty capture chambers.
- Upstream candidate localization feeding geometric normalization pipelines.

### 2.2 Explicit Out-of-Scope & Prohibited Uses
- **Food Safety Certification:** The model **must not** be used to certify eggs as safe for human consumption, Salmonella-free, or pathogen-free.
- **Candling Freshness or Haugh Unit Estimation:** This model operates solely on exterior visible-spectrum RGB images. It does **not** estimate internal albumen quality, yolk degradation, or Haugh Unit.
- **Commercial High-Speed Sorting:** Not validated for high-speed industrial sorting ($> 60\,\text{eggs/minute}$).

---

## 3. Training & Validation Data

- **Primary Dataset:** [`afshin-dini/Egg-Detection`](https://huggingface.co/datasets/afshin-dini/Egg-Detection) (Hugging Face).
- **Pinned Revision:** `d425996c959623b3960fca27f53b16f060b0a474` (MIT License).
- **Total Corpus:** 51 images, 423 annotated egg instances.
- **Classes:** Original classes `white-egg` (229) and `brown-egg` (194) mapped to canonical class `0: egg`.
- **Partitioning Protocol (Seed 42):**
  - **Train Partition (70%):** 36 images, 306 bounding boxes.
  - **Validation Partition (15%):** 8 images, 73 bounding boxes.
  - **Held-Out Test Partition (15%):** 7 images, 44 bounding boxes.
- **Scientific Disclosure on Partitioning:** Splitting is performed at the **image level** because physical egg specimen identifiers were not tracked across frames in the external source dataset. Zero SHA-256 image overlap is mathematically proven between partitions.

---

## 4. Quantitative Performance on Held-Out Test Split

Evaluation performed on strictly isolated test split (7 images, 44 egg instances, `conf=0.25`, `iou=0.50`):

| Metric | Target Baseline | Measured Value | Validation Status |
| :--- | :--- | :--- | :--- |
| **mAP@0.50** | $\ge 0.5000$ | **0.9950** | **PASSED** |
| **mAP@0.50:0.95** | $\ge 0.5000$ | **0.9400** | **PASSED** |
| **Precision** | $\ge 0.8000$ | **1.0000** | **PASSED** |
| **Recall** | $\ge 0.8000$ | **1.0000** | **PASSED** |
| **F1 Score** | $\ge 0.8000$ | **1.0000** | **PASSED** |
| **True Positives** | — | **44** | — |
| **False Positives** | — | **0** | — |
| **False Negatives** | — | **0** | — |
| **Mean Inference Latency** | $\le 500\,\text{ms}$ | **199.54 ms** | **PASSED** |
| **p95 Latency** | $\le 500\,\text{ms}$ | **207.95 ms** | **PASSED** |

*Hardware during evaluation:* AMD Ryzen 7 7435HS CPU (8 cores / 16 threads). Lightweight deployment footprint: ~6.5 MB model weights.

Visual prediction plots on test images are archived at `ml/artifacts/detection/sample_predictions.png`.

---

## 5. Architectural Integration & Fallback Strategy

- The model is registered via `ml/inference/detection_engine.py` implementing `InferenceEngine`.
- **Safe Fallback:** If weights are missing, 0 bytes, or fail SHA-256 verification, `get_inference_engine()` automatically falls back to `PlaceholderEngine` returning `status: "model_not_ready"` without runtime crashes.
- **Scientific Integrity:** The inference adapter reports detection bounding boxes and confidence while leaving candling freshness parameters (`freshness_class`, `freshness_score`, `predicted_haugh_unit`) as `None`, explicitly disclosing that candling hardware is required for internal quality metrics.

---

## 6. Ethical Considerations & Consumer Safety Disclaimers

1. **Anti-Hallucination Guarantee:** EggVision never synthesizes artificial predictions or fabricates freshness grades when unmeasured.
2. **Foodborne Pathogen Risk:** Optical detection confirms egg presence and outer boundary geometry only; it cannot guarantee biological safety or detect Salmonella.
3. **Data Provenance:** Training parameters, data splits, and model checkpoints are immutably fingerprinted with SHA-256 digests.
