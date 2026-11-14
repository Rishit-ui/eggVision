# EggVision AI — Dataset Acquisition, Annotation & Provenance Guide

## 1. Overview
EggVision AI requires validated, rigorously annotated datasets to progress beyond non-ML candidate contour screening. This document specifies the acquisition guidelines, licensing constraints, annotation schemas, and validation standards for all training pipelines.

---

## 2. Integrated Model A Dataset: `afshin-dini/Egg-Detection`
As part of Phase 1 and Phase 1.1 Foundation, EggVision AI incorporates the verified open-source egg detection dataset from Hugging Face:
- **Repository:** [`afshin-dini/Egg-Detection`](https://huggingface.co/datasets/afshin-dini/Egg-Detection)
- **License:** MIT License
- **Pinned Git Revision:** `d425996c959623b3960fca27f53b16f060b0a474`
- **Total Images:** 51
- **Total Bounding Boxes:** 423
- **Original Classes:** `0: white-egg` (229 boxes), `1: brown-egg` (194 boxes)
- **Target Mapped Class:** `0: egg` (423 boxes)
- **Scientific Splitting Disclosure:** Partitioned at the **image level** (seed = 42) into 70% Train (36 images / 306 boxes), 15% Validation (8 images / 73 boxes), and 15% Held-Out Test (7 images / 44 boxes). Specimen-level tracking is unavailable in this source dataset. Zero SHA-256 image overlap is mathematically verified across all splits.

---

## 3. Model Roles & Dataset Requirements

### Model A — Egg Detection
- **Objective:** Screen whether an egg is present, locate bounding box, reject non-egg objects.
- **Classes:** `egg` (class 0)
- **Annotation Format:** YOLO Detection (`<class_id> <x_center> <y_center> <width> <height>` normalized to [0.0, 1.0]).
- **Diversity Requirements:** White, brown, dark brown, cream, and speckled shells on diverse surfaces.

### Model B — Egg Segmentation
- **Objective:** Pixel-level binary mask separating shell from background, cast shadows, and reflections.
- **Classes:** `egg_shell` (class 0)
- **Annotation Format:** YOLO Segmentation polygons or COCO RLE/polygons.
- **Boundary Precision:** Sub-pixel contour following true calcium carbonate shell boundary.

### Model C — Visible Surface Defect Detection
- **Objective:** Detect visible external defects.
- **Classes:**
  - `0: intact_shell`
  - `1: crack_hairline`
  - `2: crack_punctured`
  - `3: severe_breakage`
  - `4: abnormal_stain`
- **Annotation Format:** YOLO Bounding Box / Polygon with defect category.

### Model D — Egg Quality & Freshness Classification
- **Scientific Constraint:** Normal exterior RGB photographs cannot determine internal microbial contamination, Salmonella presence, or Haugh Unit without destructive breakout or calibrated multi-wavelength candling instruments.
- **Requirement:** Ground-truth labels must originate from calibrated laboratory candling chambers with verified post-capture breakout measurements (albumen height in mm, weight in g).

---

## 4. Directory Structure
```
ml/data/
  ├── external/
  │   └── afshin-dini-egg-detection/
  │       ├── raw/images/        # Original downloaded images (51 samples)
  │       ├── raw/labels/        # Original YOLO labels (classes 0, 1)
  │       ├── raw/mapped_labels/ # Normalized YOLO labels (class 0: egg)
  │       └── import_report.json # Provenance & SHA-256 verification
  ├── processed/
  │   └── egg_detection_yolo/
  │       ├── images/            # train (36), val (8), test (7)
  │       ├── labels/            # train (306 boxes), val (73), test (44)
  │       ├── data.yaml          # Ultralytics dataset configuration
  │       └── split_summary.json # Zero-leakage verification & split statistics
  ├── reports/
  │   └── dataset_validation_report.json # Comprehensive integrity audit
  └── raw/                       # Legacy Open Images sample captures & metadata
```

---

## 5. Dataset Pipeline Reproduction Workflow

### 1. Import Hugging Face Dataset
```bash
python ml/scripts/import_hf_egg_detection.py
```

### 2. Validate Dataset Integrity
```bash
python ml/scripts/validate_dataset.py
```

### 3. Generate Reproducible 70/15/15 Split
```bash
python ml/scripts/split_dataset.py --seed 42
```

### 4. Train Model A (Egg Detection)
```bash
python ml/scripts/train_detection.py --epochs 30 --batch-size 8
```

### 5. Evaluate on Held-Out Test Split
```bash
python ml/scripts/evaluate_models.py
```
