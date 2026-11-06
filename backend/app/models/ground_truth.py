import uuid
from datetime import datetime

from app.models.base import Base
from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column


class GroundTruth(Base):
    __tablename__ = "ground_truth"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    egg_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("eggs.id"), nullable=False)
    haugh_unit: Mapped[float | None] = mapped_column(Float, nullable=True)
    albumen_ph: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    observations: Mapped[str | None] = mapped_column(Text, nullable=True)
    measured_by: Mapped[str | None] = mapped_column(String, nullable=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
