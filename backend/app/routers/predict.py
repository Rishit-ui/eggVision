import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.prediction import PredictRequest, PredictionResponse
from app.services.scan_service import scan_service
from app.services.prediction_service import prediction_service

router = APIRouter(tags=["Predict"])

@router.post("/predict", response_model=PredictionResponse)
async def predict_scan(
    request: PredictRequest,
    db: AsyncSession = Depends(get_db)
):
    scan = await scan_service.get_scan(db, request.scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.image_quality not in {"GOOD", "ACCEPTABLE"} or "MULTIPLE_EGGS_DETECTED" in (scan.image_quality_warnings or []):
        raise HTTPException(
            status_code=409,
            detail="Prediction blocked: image quality did not pass the required scan gate. Retake the image before analysis.",
        )

    prediction = await prediction_service.create_prediction(db, request.scan_id)
    return prediction
