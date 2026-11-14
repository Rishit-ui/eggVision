import logging
import uuid
from typing import Any

from app.models.prediction import Prediction
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ml.inference.detection_engine import get_inference_engine

logger = logging.getLogger("prediction_service")
_inference_engine = None


def get_current_inference_engine():
    global _inference_engine
    if _inference_engine is None or not _inference_engine.is_ready():
        _inference_engine = get_inference_engine()
    return _inference_engine


inference_engine = get_current_inference_engine()


class PredictionService:
    def get_engine(self):
        return get_current_inference_engine()

    async def create_prediction(
        self,
        db: AsyncSession,
        scan_id: uuid.UUID,
        image: Any | None = None,
    ) -> Prediction:
        existing = await self.get_prediction_by_scan_id(db, scan_id)
        if existing:
            return existing

        engine = self.get_engine()
        model_info = engine.get_model_info()

        if engine.is_ready() and image is not None:
            # Run real detection on provided image
            res = await engine.predict(image)
            status = "COMPLETED" if res.status == "completed" else "FAILED"
            prediction = Prediction(
                scan_id=scan_id,
                status=status,
                model_version=res.model_version or model_info.version,
                confidence=res.confidence,
                inference_time_ms=res.inference_time_ms,
                explanation={
                    "detection_details": res.explanation,
                    "inference_time_ms": res.inference_time_ms,
                    "model_status": "VALIDATED",
                },
            )
        elif engine.is_ready():
            # Model is ready in registry; awaiting image upload inference
            prediction = Prediction(
                scan_id=scan_id,
                status="READY",
                model_version=model_info.version,
                explanation={
                    "model": model_info.version,
                    "model_type": model_info.model_type,
                    "notice": "Detection model is verified and ready for image input.",
                },
            )
        else:
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
