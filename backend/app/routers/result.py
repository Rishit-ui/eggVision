import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.scan import ScanResponse
from app.services.scan_service import scan_service
from app.services.prediction_service import prediction_service
from app.schemas.scan import PredictionResponse

router = APIRouter(tags=["Result"])

@router.get("/result/{scan_id}", response_model=ScanResponse)
async def get_result(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    scan = await scan_service.get_scan(db, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
        
    prediction = await prediction_service.get_prediction_by_scan_id(db, scan_id)
    
    # We must construct a dict or object that matches the ScanResponse model
    scan_response_data = {
        "id": scan.id,
        "egg_id": scan.egg_id,
        "batch_id": scan.batch_id,
        "original_image_url": scan.original_image_url,
        "image_quality": scan.image_quality,
        "image_quality_score": scan.image_quality_score,
        "capture_date": scan.capture_date,
        "created_at": scan.created_at,
    }
    
    if prediction:
        scan_response_data["prediction"] = prediction
        
    return ScanResponse(**scan_response_data)
