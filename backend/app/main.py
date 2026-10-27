from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

from app.middleware.auth import get_current_user
from app.routers import artifacts, auth, health, scan, predict, result, history, batch, dashboard, analytics, model_info, research
from app.services.storage_service import storage_service

@asynccontextmanager
async def lifespan(app: FastAPI):
    await storage_service.ensure_ready()
    yield

app = FastAPI(
    title="EggVision AI API",
    description="Backend API for EggVision AI freshness detection",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
protected = [Depends(get_current_user)]
app.include_router(artifacts.router, prefix="/api/v1", dependencies=protected)
app.include_router(scan.router, prefix="/api/v1", dependencies=protected)
app.include_router(predict.router, prefix="/api/v1", dependencies=protected)
app.include_router(result.router, prefix="/api/v1", dependencies=protected)
app.include_router(history.router, prefix="/api/v1", dependencies=protected)
app.include_router(batch.router, prefix="/api/v1", dependencies=protected)
app.include_router(dashboard.router, prefix="/api/v1", dependencies=protected)
app.include_router(analytics.router, prefix="/api/v1", dependencies=protected)
app.include_router(model_info.router, prefix="/api/v1", dependencies=protected)
app.include_router(research.router, prefix="/api/v1", dependencies=protected)
import os
from fastapi.staticfiles import StaticFiles

upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")
