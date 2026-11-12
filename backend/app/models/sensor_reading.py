import uuid
from datetime import datetime

from app.models.base import Base
from sqlalchemy import DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("devices.id"), nullable=True)
    scan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("scans.id"), nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    ambient_light: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
