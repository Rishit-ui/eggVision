import logging

import cv2
import numpy as np
from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.prediction import PredictionResponse, PredictRequest
from app.services.prediction_service import prediction_service
from app.services.scan_service import scan_service
from app.services.storage_service import storage_service
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["Predict"])
logger = logging.getLogger(__name__)


def extract_storage_key(url: str | None) -> str | None:
    """Safely extract and sanitize storage object key from original_image_url."""
    if not url:
        return None
    cleaned = url.strip().replace("\\", "/")
    if cleaned.startswith("/api/v1/artifacts/"):
        cleaned = cleaned[len("/api/v1/artifacts/"):]
    elif cleaned.startswith("/uploads/"):
        cleaned = cleaned[len("/uploads/"):]
    parts = cleaned.strip("/").split("/")
    if any(p in {".", "..", ""} for p in parts):
        return None
    return cleaned.strip("/")


@router.post("/predict", response_model=PredictionResponse)
async def predict_scan(
    request: PredictRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    scan = await scan_service.get_scan(db, request.scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Image quality gates: reject corrupted, blurry, or over-dense images
    if scan.image_quality not in {"GOOD", "ACCEPTABLE"} or "MULTIPLE_EGGS_DETECTED" in (
        scan.image_quality_warnings or []
    ):
        raise HTTPException(
            status_code=409,
            detail="Prediction blocked: image quality did not pass the required scan gate. Retake the image before analysis.",
        )

    # Securely retrieve original scan image from object storage and decode to BGR numpy array
    image_array = None
    storage_key = extract_storage_key(scan.original_image_url)
    if storage_key:
        try:
            file_bytes, _ = await storage_service.get_image(storage_key)
            nparr = np.frombuffer(file_bytes, np.uint8)
            image_array = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            logger.warning(
                "Could not retrieve or decode original image for scan %s (key=%s): %s",
                scan.id,
                storage_key,
                e,
            )

    prediction = await prediction_service.create_prediction(
        db, scan_id=request.scan_id, image=image_array
    )
    return prediction
