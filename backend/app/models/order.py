import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Order(Base):
    """
    One order = one shop. If a customer's cart has items from three
    different shops, checkout creates three Order rows, not one — this is
    standard for multi-vendor marketplaces, and matches the "platform,
    not seller" model: the platform never bundles two shops' fulfillment
    into a single order.

    status flow: pending -> confirmed (payment succeeded)
                          -> payment_failed (payment failed, stock released)
    More statuses (shipped, delivered, cancelled) get added in later phases.
    """

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="RESTRICT"), index=True
    )

    status: Mapped[str] = mapped_column(String, default="pending", server_default="pending")
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    delivery_address: Mapped[str] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
