import uuid
from datetime import datetime

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Shop(Base):
    """
    A shop is owned by exactly one profile (the seller). Every product
    belongs to a shop, never directly to a user — this is what makes the
    "platform, not seller" model concrete in the data: the platform never
    owns inventory, a shop does.
    """

    __tablename__ = "shops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True
    )

    rating: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    # Admin can deactivate a shop (Phase 6) without deleting its data.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
