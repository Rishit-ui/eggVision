from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from app.schemas.health import HealthResponse, ServiceStatus
from app.config import settings

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"
        
    return HealthResponse(
        status="ok" if db_status == "ok" else "error",
        database=ServiceStatus(status=db_status),
        redis=ServiceStatus(status="ok"),  # Stub
        storage=ServiceStatus(status="ok"),  # Stub
        model_service=ServiceStatus(status="not_ready")  # Stub
    )
