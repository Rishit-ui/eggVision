import uuid
from datetime import date, datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, ForeignKey, Date, DateTime, func
from app.models.base import Base

class Egg(Base):
    __tablename__ = "eggs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    egg_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    farm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farms.id"), nullable=True)
    egg_type: Mapped[str | None] = mapped_column(String, nullable=True)
    laying_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    storage_condition: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
