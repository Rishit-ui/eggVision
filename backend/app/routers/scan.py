import uuid
import json
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas.scan import ScanResponse, ScanCreate
from app.services.storage_service import storage_service
from app.services.image_service import image_service
from app.services.scan_service import scan_service
from app.services.cv_service import cv_service

router = APIRouter(tags=["Scan"])

@router.post("/scan", response_model=ScanResponse, status_code=201)
async def create_scan(
    image: UploadFile = File(...),
    metadata: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        metadata_dict = json.loads(metadata)
        scan_create = ScanCreate(**metadata_dict)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid metadata format")

    file_data = await image.read()
    
    is_valid, msg = image_service.validate_image(file_data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)
        
    content_type, extension = image_service.canonical_upload_details(file_data)
    filename = f"{uuid.uuid4()}{extension}"
    original_image_url = await storage_service.upload_image(file_data, filename, content_type)
    
    # Run Computer Vision Quality, Detection, Segmentation & Normalization Pipeline
    cv_res = await cv_service.process_scan_image(file_data, image.filename)

    camera_metadata = scan_create.camera_metadata or {}
    if cv_res.get("geometry"):
        camera_metadata["egg_geometry"] = cv_res["geometry"]
    if cv_res.get("metrics"):
        camera_metadata["cv_metrics"] = cv_res["metrics"]

    scan = await scan_service.create_scan(
        db=db,
        image_url=original_image_url,
        metadata=scan_create,
        processed_image_url=cv_res.get("processed_image_url"),
        image_quality=cv_res.get("image_quality"),
        image_quality_score=cv_res.get("quality_score"),
        image_quality_warnings=cv_res.get("warnings", []),
        camera_metadata=camera_metadata,
    )

    # Return complete response including dynamic gating fields
    response_data = ScanResponse.model_validate(scan).model_dump()
    response_data["retake_recommended"] = cv_res.get("retake_recommended", False)
    response_data["recommendation"] = cv_res.get("recommendation")
    response_data["egg_geometry"] = cv_res.get("geometry")

    return ScanResponse(**response_data)
