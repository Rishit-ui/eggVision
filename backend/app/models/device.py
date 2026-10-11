import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from app.models.base import Base

class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    device_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farms.id"), nullable=True)
    firmware_version: Mapped[str | None] = mapped_column(String, nullable=True)
    software_version: Mapped[str | None] = mapped_column(String, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String, nullable=True)
    camera_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    hardware_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_status: Mapped[str] = mapped_column(String, default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
