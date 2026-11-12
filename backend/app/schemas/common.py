from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

class StatusResponse(BaseModel):
    status: str
    message: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    model_config = ConfigDict(from_attributes=True)

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
    pages: int
    
    model_config = ConfigDict(from_attributes=True)


class CountByLabel(BaseModel):
    label: str
    count: int
