# EggVision AI System Architecture

## Overview
EggVision AI analyzes images of eggs taken in a controlled physical chamber and uses machine learning to predict freshness and detect defects.

## Data Flow
```
Physical Device → Camera → Image Quality → Egg Detection → Segmentation → 
Normalization → Feature Extraction → Vision Model → Fusion Model → API → Web UI → Database
```

## Components
- **Physical Device**: Controlled lighting scanning chamber (see hardware.md).
- **Camera**: RGB sensor capturing egg images.
- **Image Quality**: Pre-check for blur and lighting.
- **Egg Detection & Segmentation**: Isolates the egg from the background.
- **Normalization**: Standardizes size, orientation, and color.
- **Feature Extraction**: Air cell detection, yolk detection, crack detection.
- **Vision Model**: CNN/Transformer evaluating visual features.
- **Fusion Model**: Combines visual embeddings with metadata (temp, age).
- **API**: FastAPI backend.
- **Web UI**: Next.js dashboard.
- **Database**: PostgreSQL for structured data, MinIO for images.

## Technology Choices
FastAPI and PyTorch provide a performant ML backend, while Next.js offers a responsive user interface.

## Trust boundary and release gate

The OpenCV pipeline is an image-quality and geometry pre-processing component, not a clinically or food-safety validated freshness classifier. It may reject unusable images, but it does not establish edible quality, pathogen absence, exact egg age, Haugh Unit, yolk state, crack absence, or blood-spot absence.

`MODEL_NOT_READY` is the required response until a model is registered with a versioned dataset, held-out evaluation report, calibrated uncertainty thresholds, and documented operating limits. Quality-gate failures must never be sent to inference. A production release also requires authentication/authorization, secret rotation, TLS termination, private database/object-storage networking, backups, monitoring, and an incident-response owner.
