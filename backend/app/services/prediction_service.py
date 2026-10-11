import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.prediction import Prediction

class PredictionService:
    async def create_prediction(self, db: AsyncSession, scan_id: uuid.UUID) -> Prediction:
        prediction = Prediction(
            scan_id=scan_id,
            status="MODEL_NOT_READY"
        )
        db.add(prediction)
        await db.commit()
        await db.refresh(prediction)
        return prediction
        
    async def get_prediction(self, db: AsyncSession, prediction_id: uuid.UUID) -> Prediction | None:
        result = await db.execute(select(Prediction).filter(Prediction.id == prediction_id))
        return result.scalar_one_or_none()
        
    async def get_prediction_by_scan_id(self, db: AsyncSession, scan_id: uuid.UUID) -> Prediction | None:
        result = await db.execute(select(Prediction).filter(Prediction.scan_id == scan_id))
        return result.scalar_one_or_none()

prediction_service = PredictionService()
