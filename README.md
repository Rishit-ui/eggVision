# EggVision 🥚

**AI-Powered Egg Quality Detection System**

🌐 **Live Website:** [Visit EggVision](https://egg-vision-1n2a.vercel.app/)

EggVision uses AI and computer vision to analyze egg quality and help identify visible defects.

## Features
- AI-powered egg quality detection
- Interactive web interface
- Automated image analysisatform

![Project status](https://img.shields.io/badge/status-model%20validation%20pending-amber)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11-blue)
![Node](https://img.shields.io/badge/node-20-green)

EggVision AI is a production-oriented research platform for controlled egg-candling capture, image-quality gating, and future validated quality estimation. It currently performs image-quality and egg-geometry processing; it deliberately returns `MODEL_NOT_READY` rather than producing a freshness, age, Haugh Unit, crack, or safety claim until a trained model has passed the documented release gate.

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
| ML Pipeline | OpenCV quality and geometry baseline; validated model pending |
| Infrastructure | Docker, Docker Compose, GitHub Actions |

## Quick Start
For Windows installation and launch instructions, see [the local run guide](docs/run-local-windows.md). To start the local stack after configuring `.env`:
```bash
docker compose up --build
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

## Delivery status

See [project status](docs/project-status.md) for an evidence-based completion estimate, current capabilities, and the model-validation work required before freshness predictions can be enabled.
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
This system is an experimental AI tool. It is **not a guarantee of food safety** and does not detect pathogens or establish that an egg is edible. Do not consume eggs that appear spoiled regardless of a future model prediction. See [research validation requirements](docs/research.md) before enabling any prediction model.

## License
MIT

## Contributing
Contributions are welcome. Please check out the issues page and submit pull requests.
