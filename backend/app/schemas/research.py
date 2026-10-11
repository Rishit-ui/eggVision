import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class EggCreate(BaseModel):
    egg_id: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    farm_id: uuid.UUID | None = None
    egg_type: str | None = Field(default=None, max_length=60)
    laying_date: date | None = None
    storage_condition: str | None = Field(default=None, max_length=100)


class EggResponse(EggCreate):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroundTruthCreate(BaseModel):
    egg_id: uuid.UUID
    haugh_unit: float | None = Field(default=None, ge=0, le=130)
    albumen_ph: float | None = Field(default=None, ge=0, le=14)
    weight: float | None = Field(default=None, gt=0, le=200)
    observations: str | None = Field(default=None, max_length=2_000)
    measured_by: str | None = Field(default=None, max_length=200)
    measured_at: datetime | None = None


class GroundTruthResponse(GroundTruthCreate):
    id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
