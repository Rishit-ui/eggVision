import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from .scan import PredictionResponse

class PredictRequest(BaseModel):
    scan_id: uuid.UUID
    
    model_config = ConfigDict(from_attributes=True)

class ModelInfoResponse(BaseModel):
    model_version: str
    model_type: str | None = None
    is_ready: bool = False
    description: str | None = None
    dataset_version: str | None = None
    metrics: dict | None = None
    trained_at: datetime | None = None
    
    model_config = ConfigDict(from_attributes=True)
