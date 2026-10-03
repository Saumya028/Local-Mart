import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Payment(Base):
    """
    One row per order. Payments are made DIRECTLY from the customer to the
    shop (UPI or cash) — the platform never touches the money, so it can
    only record what the two parties tell it.

    status flow:
      upi:  unpaid -> submitted (customer says they paid) -> paid (shop confirmed)
                                                          -> unpaid (shop says "not received")
      cash: unpaid -> paid (auto, when the shop marks the order delivered/picked up)

    Rows created back when this app used Razorpay keep their old
    `provider_ref` (a Razorpay order id); migration 0016 converted their
    "succeeded" status to "paid". New rows leave provider_ref null.
    """

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )

    provider_ref: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    status: Mapped[str] = mapped_column(String, default="unpaid", server_default="unpaid")
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    # "upi" or "cash" (legacy rows may say "card")
    method: Mapped[str] = mapped_column(String, default="upi", server_default="upi")

    # UTR / transaction id the customer typed in when they said they paid.
    payer_reference: Mapped[str | None] = mapped_column(String, nullable=True)
    # When the customer pressed "I've paid".
    marked_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # When the shop confirmed receipt (or cash was collected).
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
