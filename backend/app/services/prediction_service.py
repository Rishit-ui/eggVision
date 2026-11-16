import logging
import uuid
from typing import Any

from app.models.prediction import Prediction
from app.services.model_loader import model_manager
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("prediction_service")


def get_current_inference_engine():
    """Use only the lifecycle manager's integrity-verified engine."""
    return model_manager.get_engine()


class _EngineProxy:
    """Proxy object so module-level inference_engine always delegates to current engine."""

    def is_ready(self) -> bool:
        return get_current_inference_engine().is_ready()

    def get_model_info(self):
        return get_current_inference_engine().get_model_info()

    async def predict(self, *args, **kwargs):
        return await get_current_inference_engine().predict(*args, **kwargs)


inference_engine = _EngineProxy()


class PredictionService:
    def get_engine(self):
        return get_current_inference_engine()

    async def create_prediction(
        self,
        db: AsyncSession,
        scan_id: uuid.UUID,
        image: Any | None = None,
        force: bool = False,
    ) -> Prediction:
        existing = await self.get_prediction_by_scan_id(db, scan_id)
        # Preserve a completed structured detection result. Older records that
        # only contain legacy prose are eligible for a fresh detector run.
        if (
            not force
            and existing
            and existing.status == "COMPLETED"
            and isinstance(existing.explanation, dict)
            and existing.explanation.get("task") == "visible_shell_detection"
            and isinstance(existing.explanation.get("detections"), list)
        ):
            return existing

        engine = self.get_engine()
        model_info = engine.get_model_info()

        if engine.is_ready() and image is not None:
            result = await engine.predict(image)
            if result.status == "completed":
                status = "COMPLETED"
                explanation = {
                    "task": "visible_shell_detection",
                    "model_status": "READY",
                    "detection_count": len(result.detections),
                    "detections": result.detections,
                    "diagnostics": {
                        "confidence_threshold": result.confidence_threshold,
                        "max_candidate_confidence": result.max_candidate_confidence,
                        "candidates_above_threshold": result.candidates_above_threshold,
                    },
                    "detection_details": result.explanation,
                    "limitations": [
                        "Visible shell object localization only.",
                        "No freshness, internal quality, crack, spoilage, contamination, or food-safety assessment was performed.",
                    ],
                }
            else:
                status = "MODEL_NOT_READY" if result.status == "model_not_ready" else "FAILED"
                explanation = {
                    "task": "visible_shell_detection",
                    "model_status": status,
                    "reason": result.error_message or "The detector did not complete inference.",
                    "detection_details": result.explanation,
                }

            logger.info(
                "prediction_inference_complete scan_id=%s status=%s detections=%s "
                "max_candidate_confidence=%s threshold=%s candidates_above_threshold=%s",
                scan_id,
                status,
                len(result.detections),
                result.max_candidate_confidence,
                result.confidence_threshold,
                result.candidates_above_threshold,
            )
            values = {
                "status": status,
                "model_version": result.model_version or model_info.version,
                "confidence": result.confidence,
                "inference_time_ms": result.inference_time_ms,
                "explanation": explanation,
            }
        elif engine.is_ready():
            values = {
                "status": "IMAGE_UNAVAILABLE",
                "model_version": model_info.version,
                "confidence": None,
                "inference_time_ms": None,
                "explanation": {
                    "task": "visible_shell_detection",
                    "model_status": "READY",
                    "reason": "The original scan image could not be retrieved or decoded for inference.",
                },
            }
        else:
            values = {
                "status": "MODEL_NOT_READY",
                "model_version": model_info.version,
                "confidence": None,
                "inference_time_ms": None,
                "explanation": {
                    "task": "visible_shell_detection",
                    "model_status": "MODEL_NOT_READY",
                    "reason": "No integrity-verified detection runtime is available.",
                },
            }

        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            prediction = existing
        else:
            prediction = Prediction(scan_id=scan_id, **values)
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
