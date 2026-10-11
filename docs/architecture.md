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

## Deployment & Security
Deployed via Docker Compose. Data is segmented by user/farm with basic auth to be implemented.
