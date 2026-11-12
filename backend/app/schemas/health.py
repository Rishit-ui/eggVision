from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceStatus(BaseModel):
    status: str
    latency_ms: float | None = None
    
    model_config = ConfigDict(from_attributes=True)

class HealthResponse(BaseModel):
    status: str
    database: ServiceStatus
    redis: ServiceStatus
    storage: ServiceStatus
    model_service: ServiceStatus
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    model_config = ConfigDict(from_attributes=True)
