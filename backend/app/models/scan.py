import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, Float, func
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base

class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    egg_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("eggs.id"), nullable=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("batches.id"), nullable=True)
    device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    original_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    processed_image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    image_quality: Mapped[str | None] = mapped_column(String, nullable=True)
    image_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_quality_warnings: Mapped[list | None] = mapped_column(JSONB, default=list)
    camera_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    capture_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
