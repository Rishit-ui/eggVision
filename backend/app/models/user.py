import uuid

from app.models.base import Base, TimestampMixin
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
