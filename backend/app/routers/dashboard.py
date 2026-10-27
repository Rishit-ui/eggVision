from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.prediction import Prediction
from app.models.scan import Scan
from app.schemas.common import CountByLabel
from app.schemas.dashboard import DashboardResponse
from app.services.prediction_service import inference_engine

router = APIRouter(tags=["Dashboard"])

async def grouped_counts(db: AsyncSession, statement) -> list[CountByLabel]:
    result = await db.execute(statement)
    return [CountByLabel(label=str(label or "UNKNOWN"), count=count) for label, count in result.all()]


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    """Return observed scan data only; freshness classes stay empty until a model is validated."""
    total_scans = (await db.execute(select(func.count()).select_from(Scan))).scalar_one()
    usable_scans = (
        await db.execute(select(func.count()).select_from(Scan).where(Scan.image_quality.in_(["GOOD", "ACCEPTABLE"])))
    ).scalar_one()
    image_quality = await grouped_counts(
        db, select(Scan.image_quality, func.count()).group_by(Scan.image_quality).order_by(Scan.image_quality)
    )
    prediction_status = await grouped_counts(
        db, select(Prediction.status, func.count()).group_by(Prediction.status).order_by(Prediction.status)
    )
    freshness = await grouped_counts(
        db,
        select(Prediction.freshness_class, func.count())
        .where(Prediction.freshness_class.is_not(None))
        .group_by(Prediction.freshness_class)
        .order_by(Prediction.freshness_class),
    )
    return DashboardResponse(
        total_scans=total_scans,
        usable_scans=usable_scans,
        retake_scans=total_scans - usable_scans,
        model_ready=inference_engine.is_ready(),
        image_quality_distribution=image_quality,
        prediction_status_distribution=prediction_status,
        freshness_distribution=freshness,
    )
