# EggVision AI — Dataset Acquisition, Annotation & Provenance Guide

## 1. Overview
EggVision AI requires validated, rigorously annotated datasets to progress beyond non-ML candidate contour screening. This document specifies the acquisition guidelines, licensing constraints, annotation schemas, and validation standards for all training pipelines.

---

## 2. Model Roles & Dataset Requirements

### Model A — Egg Detection
- **Objective:** Screen whether an egg is present, locate bounding box, reject non-egg objects.
- **Classes:** `egg` (class 0)
- **Annotation Format:** YOLO Detection (`<class_id> <x_center> <y_center> <width> <height>` normalized to [0.0, 1.0]).
- **Diversity Requirements:** White, brown, dark brown, cream, and speckled shells on diverse surfaces (white, black, blue, green, grey, wood, kitchen countertops).

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

## 3. Approved Dataset Sources & Licenses
When acquiring external datasets, record:
1. Source URL and archive checksum (SHA-256).
2. License: CC BY 4.0, CC0, or approved open academic license. Commercial-use restrictions must be documented.
3. Provenance metadata (camera model, illumination wavelength in nm, sensor geometry).

---

## 4. Directory Structure
```
ml/data/
  ├── raw/               # Original immutable capture files
  ├── processed/         # Normalized canonical resolution images
  ├── annotations/       # Ground-truth labels (YOLO / COCO format)
  ├── train/             # 70% reproducible training split
  ├── validation/        # 15% tuning split
  ├── test/              # 15% held-out evaluation split (isolated)
  └── fixtures/          # Synthetic and golden test images
```

---

## 5. Dataset Validation Workflow
Run the dataset validation suite before training:
```bash
python ml/scripts/validate_dataset.py --data-dir ml/data
python ml/scripts/split_dataset.py --input-dir ml/data/processed --output-dir ml/data
```
