import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, Integer, DateTime, func
from app.models.base import Base

class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farms.id"), nullable=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    total_eggs: Mapped[int] = mapped_column(Integer, default=0)
    scanned_eggs: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
