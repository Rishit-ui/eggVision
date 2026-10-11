import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BatchCreate(BaseModel):
    batch_id: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=500)
    total_eggs: int = Field(default=0, ge=0)
    farm_id: uuid.UUID | None = None


class BatchResponse(BaseModel):
    id: uuid.UUID
    batch_id: str
    description: str | None
    total_eggs: int
    scanned_eggs: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
