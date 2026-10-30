import asyncio
import logging
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
logger = logging.getLogger(__name__)

@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    db_latency = None
    try:
        started = perf_counter()
        await asyncio.wait_for(
            db.execute(text("SELECT 1")), timeout=settings.HEALTHCHECK_TIMEOUT_SECONDS
        )
        db_latency = round((perf_counter() - started) * 1000, 2)
    except Exception as error:
        logger.warning("Database health check failed: %s", type(error).__name__)
        db_status = "error"

    redis_status = "ok"
    redis_latency = None
    client = None
    try:
        client = redis.from_url(settings.REDIS_URL)
        started = perf_counter()
        await asyncio.wait_for(client.ping(), timeout=settings.HEALTHCHECK_TIMEOUT_SECONDS)
        redis_latency = round((perf_counter() - started) * 1000, 2)
    except Exception as error:
        logger.warning("Redis health check failed: %s", type(error).__name__)
        redis_status = "error"
    finally:
        if client is not None:
            await client.aclose()

    storage_status = await storage_service.health_status()
    model_status = "ready" if inference_engine.is_ready() else "not_ready"
    service_states = (db_status, redis_status, storage_status)
    overall = "error" if "error" in service_states else ("degraded" if "degraded" in service_states or model_status != "ready" else "ok")

    return HealthResponse(
        status=overall,
        database=ServiceStatus(status=db_status, latency_ms=db_latency),
        redis=ServiceStatus(status=redis_status, latency_ms=redis_latency),
        storage=ServiceStatus(status=storage_status),
        model_service=ServiceStatus(status=model_status),
    )
