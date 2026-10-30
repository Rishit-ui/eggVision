# EggVision engineering audit

## Actual inference path (29 October 2026)

`POST /api/v1/scan` validates uploaded bytes with Pillow, decodes them with OpenCV, then runs `ml.vision.VisionPipeline`.  The pipeline uses Otsu thresholding, contour shape filters, quality heuristics, segmentation, and normalization.  It does **not** load a neural-network checkpoint, call an external AI service, use an LLM, or contain a trained egg/defect/freshness classifier.

`POST /api/v1/predict` uses `PlaceholderEngine`, which persists only `MODEL_NOT_READY` and no predicted values. There are no model weights, dataset records, annotations, training scripts, training metrics, or provenance manifest in the repository.

## Reliability issue corrected

The former contour rule exposed a shape-derived score as `confidence` and used language implying an egg had been located. A bright or egg-shaped non-egg object could therefore be mistaken for a confirmed egg. The contour stage is now explicitly a non-ML **candidate-contour screen**:

- corrupt/empty input: `INVALID_IMAGE`;
- no suitable chamber contour: `NO_EGG_DETECTED`;
- one or more compatible contours: `UNCERTAIN`;
- `EGG_DETECTED` is unavailable until a trained and validated detector is registered.

No shape-derived confidence, defect, freshness, spoilage, or safety output is returned. Candidate-contour geometry may be retained in scan metadata for research, but is not shown as verified egg geometry.

## What is required before enabling product claims

1. Register a versioned egg detector with documented source, licence, labels, preprocessing, artifact hash, and operating thresholds.
2. Evaluate it on an independent test set containing eggs, people, hands, cartons, food, egg-shaped objects, and difficult capture conditions. Report precision, recall, false-positive rate, false-negative rate, confidence calibration, and abstention coverage.
3. Add separate defect models and evaluation data for each supported defect category. A shell-defect model cannot establish internal freshness or microbiological safety.
4. Add freshness/spoilage claims only after a task-specific reference standard, ground truth, held-out evaluation, and domain approval meet the release gate in `docs/research.md`.

Until then, EggVision is a controlled capture and research-data platform, not an egg-inspection or food-safety decision system.
