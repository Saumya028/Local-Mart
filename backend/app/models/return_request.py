import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReturnRequest(Base):
    """
    A customer's request to return or exchange one line item from a
    delivered order. Scoped to a single OrderItem (not the whole order)
    because a customer who bought three different products in one order
    may only want to send one of them back — the same per-item model
    Amazon/Flipkart-style marketplaces use, rather than forcing an
    all-or-nothing return of the whole order.

    status flow: requested -> approved -> completed  (shop accepts, then
                                                        confirms the pickup/
                                                        refund or exchange
                                                        actually happened)
                 requested -> rejected                (shop declines, with
                                                        shop_note explaining
                                                        why)
                 requested -> cancelled                (customer backs out,
                                                        only before the shop
                                                        has acted)
    See app/core/return_status.py for the single source of truth on which
    of those transitions is legal from where.

    Deliberately does NOT touch the parent Order's own `status` — an
    order stays "delivered" even after one of its items is returned or
    exchanged; this row is where that separate, per-item story lives.
    """

    __tablename__ = "return_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("order_items.id", ondelete="CASCADE"), index=True
    )
    # Denormalized from the order, same reasoning as Order.shop_id itself
    # (see that model's docstring): the shop dashboard's incoming-returns
    # list filters directly on `shop_id` on every load, so it gets its
    # own index instead of requiring a join through orders every time.
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="RESTRICT"), index=True
    )

    # "return" -> refund; "exchange" -> swap for exchange_product_id.
    request_type: Mapped[str] = mapped_column(String, default="return", server_default="return")

    quantity: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)

    # Only set (and only meaningful) when request_type == "exchange" — the
    # replacement product the customer wants instead, e.g. a different
    # size/color variant of the same item. ON DELETE SET NULL rather than
    # RESTRICT: if that replacement product is later deactivated/removed,
    # the historical request should still be readable, just without a
    # resolvable target.
    exchange_product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )

    # Snapshotted at request time, same reasoning as OrderItem.unit_price
    # — what the customer is owed on a return shouldn't drift if the
    # shop changes the product's price before this gets resolved.
    refund_amount: Mapped[float] = mapped_column(Numeric(10, 2))

    status: Mapped[str] = mapped_column(
        String, default="requested", server_default="requested", index=True
    )
    # The shop owner's note back to the customer — a rejection reason, or
    # pickup/refund/exchange-shipping instructions once approved.
    shop_note: Mapped[str | None] = mapped_column(String, nullable=True)

    # --- Exchange price-difference settlement ---
    # Snapshotted at request time: (exchange product's price - original
    # unit_price) * quantity. Positive = the replacement costs more and
    # the customer owes this; negative = it costs less and the customer
    # is owed this back; zero for a same-price swap. Always 0 for a plain
    # "return" (there's no replacement item to compare against).
    price_difference: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0, server_default="0"
    )
    # Only set when price_difference > 0 — the Razorpay Order created to
    # collect that top-up, mirroring how Payment.provider_ref stores the
    # Razorpay order id for a normal checkout (see routers/orders.py's
    # `checkout`). Kept on this row rather than reusing the Payment table,
    # since Payment.order_id is NOT NULL and no Order exists yet for the
    # replacement item at request time — see new_order_id below for when
    # one finally does.
    difference_razorpay_order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Flips true once routers/returns.py's verify_difference_payment has
    # checked Razorpay's signature on that top-up payment — the same
    # signature-verification pattern as routers/orders.py's
    # verify_payment, just scoped to this smaller amount.
    difference_paid: Mapped[bool] = mapped_column(default=False, server_default="false")

    # Set once, when a shop owner marks this "completed" — the new Order
    # created for the replacement item itself (see
    # routers/shop_dashboard.py's update_return_status). Only ever set
    # for a completed exchange; a return has no replacement to ship, and
    # nothing is created until completion because that's the point the
    # shop has actually confirmed the swap is happening. ON DELETE SET
    # NULL so this historical request stays readable even if that order
    # is later purged.
    new_order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_return_requests_shop_id_created_at", "shop_id", "created_at"),
        Index("ix_return_requests_user_id_created_at", "user_id", "created_at"),
    )
