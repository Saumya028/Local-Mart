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
    From "confirmed" the pipeline forks on `fulfillment_type` — see
    app/core/order_status.py for the full delivery vs. pickup transition
    maps.
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
    # "delivery" (default — matches every order created before this
    # feature) or "pickup", set once at checkout (see routers/orders.py's
    # checkout) and never changed after. Decides which of
    # app/core/order_status.py's two transition maps this order follows.
    fulfillment_type: Mapped[str] = mapped_column(
        String, default="delivery", server_default="delivery"
    )
    # Only set for fulfillment_type="delivery" — a pickup order has
    # nowhere to deliver TO, so this stays null for one (see checkout's
    # do_checkout). Nullable rather than an empty string so "no delivery
    # address on this order" and "address snapshot was somehow blank"
    # can never be confused.
    delivery_address: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set once, the moment a shop owner (or staff) moves this order into
    # EITHER terminal status — "delivered" for a delivery order or
    # "picked_up" for a pickup one (see app/core/order_status.py's
    # TERMINAL_STATUSES) — never touched again after that. This is what
    # the return/exchange window (app/core/return_status.py's
    # RETURN_WINDOW) counts from for both fulfillment types; using
    # created_at instead would unfairly shrink the window by however long
    # the order took to actually reach the customer.
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Set the moment a delivery person (or manager/owner) marks this
    # order "delivered" — see app/core/order_status.py's
    # DELIVERY_PROOF_REQUIRED_STATUSES and routers/shop_dashboard.py's
    # update_order_status, which rejects the "delivered" transition
    # without one. A plain public-bucket URL (same pattern as
    # products.images), shown to both the shop's staff and the customer
    # on their own order-tracking page as proof the order actually
    # arrived.
    delivery_proof_photo_url: Mapped[str | None] = mapped_column(String, nullable=True)

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
