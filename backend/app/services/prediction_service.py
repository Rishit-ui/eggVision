import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.prediction import Prediction
from ml.inference.placeholder import PlaceholderEngine

inference_engine = PlaceholderEngine()

class PredictionService:
    async def create_prediction(self, db: AsyncSession, scan_id: uuid.UUID) -> Prediction:
        existing = await self.get_prediction_by_scan_id(db, scan_id)
        if existing:
            return existing

        model_info = inference_engine.get_model_info()
        prediction = Prediction(
            scan_id=scan_id,
            status="MODEL_NOT_READY",
            model_version=model_info.version,
            explanation={
                "reason": "No validated inference model is deployed.",
                "action": "Train and validate a model against held-out egg- and farm-level ground truth before enabling predictions.",
            },
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
