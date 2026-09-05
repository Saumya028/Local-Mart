import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, func
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
    # index=True (Phase 7 hardening pass): every foreign key should have
    # one, even though nothing currently filters WHERE on it directly —
    # this is the "confirm indexes exist on every foreign key" line item,
    # not just the ones already on a hot read path.
    address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True, index=True
    )

    rating: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    # Admin can deactivate a shop (Phase 6) without deleting its data.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Composite index (Phase 7): GET /shops's hottest query is exactly
    # `WHERE is_active = true ORDER BY rating DESC LIMIT 50` — this one
    # index serves both the filter and the sort together, rather than
    # Postgres using a single-column index for one and sorting the rest
    # in memory.
    __table_args__ = (Index("ix_shops_is_active_rating", "is_active", "rating"),)
