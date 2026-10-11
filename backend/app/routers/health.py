from time import perf_counter

import redis.asyncio as redis
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.schemas.health import HealthResponse, ServiceStatus
from app.config import settings
from app.services.prediction_service import inference_engine
from app.services.storage_service import storage_service

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    db_latency = None
    try:
        started = perf_counter()
        await db.execute(text("SELECT 1"))
        db_latency = round((perf_counter() - started) * 1000, 2)
    except Exception:
        db_status = "error"

    redis_status = "ok"
    redis_latency = None
    try:
        client = redis.from_url(settings.REDIS_URL)
        started = perf_counter()
        await client.ping()
        redis_latency = round((perf_counter() - started) * 1000, 2)
        await client.aclose()
    except Exception:
        redis_status = "error"

    storage_status = await storage_service.health_status()
    model_status = "ready" if inference_engine.is_ready() else "not_ready"
    overall = "error" if db_status != "ok" or storage_status == "error" else "degraded" if storage_status == "degraded" else "ok"

    return HealthResponse(
        status=overall,
        database=ServiceStatus(status=db_status, latency_ms=db_latency),
        redis=ServiceStatus(status=redis_status, latency_ms=redis_latency),
        storage=ServiceStatus(status=storage_status),
        model_service=ServiceStatus(status=model_status),
    )
