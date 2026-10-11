# Training Methodology

## Baselines
We evaluate against 5 baseline experiments before moving to complex models:
1. Metadata-only Random Forest
2. Simple CNN (ResNet18) on raw images
3. Features-only XGBoost
4. Base Vision Transformer
5. Multimodal Fusion (Image + Metadata)

## Ablation Study Design
Analyze the contribution of segmentation, normalization, and metadata to the final accuracy.

## Evaluation Metrics
- **Classification**: Freshness class (Fresh, Semi-Fresh, Spoiled) using Accuracy, F1-score
- **Regression**: Haugh unit prediction using MAE, RMSE
- **Detection**: Crack bounding boxes (mAP)
- **Segmentation**: Air cell and yolk (IoU)

## Model Versioning
Use MLflow to track parameters, metrics, and models.

## Reproducibility
All experiments must fix random seeds and record exact dataset versions.
