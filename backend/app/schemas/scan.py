import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict

class ScanCreate(BaseModel):
    egg_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    device_id: uuid.UUID | None = None
    camera_metadata: dict[str, Any] | None = None
    temperature: float | None = None
    humidity: float | None = None
    egg_type: str | None = None
    storage_condition: str | None = None
    
    model_config = ConfigDict(from_attributes=True)


class UploadUrlRequest(BaseModel):
    filename: str
    content_type: str = "image/jpeg"
    file_size: int | None = None


class UploadUrlResponse(BaseModel):
    upload_url: str
    object_key: str
    public_url: str | None = None
    expires_in: int = 300


class DirectScanCreate(BaseModel):
    object_key: str
    metadata: ScanCreate = ScanCreate()

class PredictionResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    freshness_class: str | None = None
    freshness_score: float | None = None
    estimated_age_min: int | None = None
    estimated_age_max: int | None = None
    predicted_haugh_unit: float | None = None
    confidence: float | None = None
    air_cell_area: float | None = None
    air_cell_ratio: float | None = None
    yolk_visibility: str | None = None
    crack_probability: float | None = None
    blood_spot_probability: float | None = None
    explanation: dict | list[str] | None = None
    heatmap_url: str | None = None
    model_version: str | None = None
    inference_time_ms: float | None = None
    status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ScanResponse(BaseModel):
    id: uuid.UUID
    egg_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None
    original_image_url: str | None = None
    processed_image_url: str | None = None
    image_quality: str | None = None
    # Deprecated persistence field; no longer a quality/confidence percentage.
    image_quality_score: float | None = None
    image_quality_warnings: list[str] = []
    retake_recommended: bool = False
    recommendation: str | None = None
    analysis: dict[str, Any] | None = None
    candidate_contour_geometry: dict[str, Any] | None = None
    egg_geometry: dict[str, Any] | None = None
    capture_date: datetime
    created_at: datetime
    prediction: PredictionResponse | None = None
    
    model_config = ConfigDict(from_attributes=True)

class ScanListResponse(BaseModel):
    items: list[ScanResponse]
    
    model_config = ConfigDict(from_attributes=True)
