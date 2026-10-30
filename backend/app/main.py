import logging
import sys
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import close_database

from app.middleware.auth import get_current_user
from app.routers import artifacts, auth, health, scan, predict, result, history, batch, dashboard, analytics, model_info, research
from app.services.storage_service import storage_service

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting EggVision API (python=%s, environment=%s)", sys.version.split()[0], settings.APP_ENV)
    await storage_service.ensure_ready()
    try:
        yield
    finally:
        await close_database()

app = FastAPI(
    title="EggVision AI API",
    description="Backend API for controlled candling capture and research evidence collection",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
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
# Local artifact URLs are convenient for development.  Production fallback
# artifacts are served through the authenticated artifacts router instead.
if settings.APP_ENV.lower() != "production":
    app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")
