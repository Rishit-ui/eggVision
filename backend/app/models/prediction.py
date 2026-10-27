import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, Float, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base

class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scans.id"), nullable=False)
    freshness_class: Mapped[str | None] = mapped_column(String, nullable=True)
    freshness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_age_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_age_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    predicted_haugh_unit: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    air_cell_area: Mapped[float | None] = mapped_column(Float, nullable=True)
    air_cell_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    yolk_visibility: Mapped[str | None] = mapped_column(String, nullable=True)
    crack_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    blood_spot_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    explanation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    heatmap_url: Mapped[str | None] = mapped_column(String, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    inference_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
