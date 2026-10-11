# 🥚 EggVision AI
### AI-Powered Non-Destructive Egg Freshness Detection Platform

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Node](https://img.shields.io/badge/node-20-green)

EggVision AI is an intelligent platform designed for non-destructive assessment of egg freshness. By combining affordable hardware scanning chambers with advanced computer vision models, it can predict egg freshness and physical traits.

## Architecture Overview
```
Camera → Image Quality → Egg Detection → Segmentation → 
Normalization → Feature Extraction → AI Model → API → Web UI → Database
```

## Tech Stack
| Component | Technologies |
| --- | --- |
| Frontend | Next.js, React, Node 20 |
| Backend | FastAPI, Python 3.11, PostgreSQL, Redis, MinIO |
| ML Pipeline | PyTorch, OpenCV, ONNX Runtime, MLflow |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

## Quick Start
To start the entire stack locally using Docker Compose:
```bash
docker-compose up -d
```

## Development Setup
### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Project Structure
```
.
├── backend/       # FastAPI application
├── frontend/      # Next.js frontend
├── ml/            # Machine learning pipeline and inference engine
├── hardware/      # Physical scanning chamber designs
├── docs/          # Project documentation
├── scripts/       # Utility scripts
└── tests/         # Unit and integration tests
```

## API Endpoints
| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/v1/health` | GET | Check system health |
| `/api/v1/scan` | POST | Upload and process an egg image |
| `/api/v1/predict` | POST | Run model inference |

## Limitations and Disclaimer
This system is an experimental AI tool. It is **not a guarantee of food safety**. Do not consume eggs that appear spoiled regardless of the model's prediction.

## License
MIT

## Contributing
Contributions are welcome. Please check out the issues page and submit pull requests.
