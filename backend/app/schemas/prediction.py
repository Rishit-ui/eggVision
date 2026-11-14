import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .scan import PredictionResponse

__all__ = ["PredictRequest", "ModelInfoResponse", "PredictionResponse"]


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
    state: str = "MODEL_NOT_READY"
    artifact_available: bool = False
    checksum_verified: bool = False
    runtime_available: bool = False
    runtime_name: str | None = None
    
    model_config = ConfigDict(from_attributes=True)
