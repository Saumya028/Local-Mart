import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func
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
    # No standalone index=True here (Phase 7): the composite indexes
    # below, on (user_id, created_at) and (shop_id, created_at), already
    # cover plain "WHERE user_id = X" / "WHERE shop_id = X" lookups via
    # their leftmost column — a separate single-column index on the same
    # column would just be redundant write overhead with no query it
    # alone serves better.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE")
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="RESTRICT")
    )

    # index=True (Phase 7 hardening pass): filtered directly in
    # admin.py's platform_metrics (`WHERE status = 'confirmed'`) and in
    # shop_dashboard.py's sales_summary aggregate.
    status: Mapped[str] = mapped_column(
        String, default="pending", server_default="pending", index=True
    )
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    delivery_address: Mapped[str] = mapped_column(String)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Composite indexes (Phase 7): order history (`GET /orders`) and the
    # Shop Dashboard's order list (`GET /dashboard/orders`) both do
    # exactly "WHERE user_id/shop_id = X ORDER BY created_at DESC" — a
    # composite index serves the filter and the sort in one index scan,
    # rather than the single-column index on user_id/shop_id alone
    # (already there for the FK) requiring a separate sort step once the
    # matching rows grow past what fits comfortably in memory.
    __table_args__ = (
        Index("ix_orders_user_id_created_at", "user_id", "created_at"),
        Index("ix_orders_shop_id_created_at", "shop_id", "created_at"),
    )
