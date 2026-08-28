import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Payment(Base):
    """
    One row per order, even when several orders share a single Stripe
    PaymentIntent (a multi-shop checkout pays for everything in one card
    charge, but we still track success/failure per order). `provider_ref`
    is what the Stripe webhook uses to find which payments to update.
    """

    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )

    provider_ref: Mapped[str] = mapped_column(String, index=True)  # Stripe PaymentIntent ID
    status: Mapped[str] = mapped_column(String, default="pending", server_default="pending")
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    method: Mapped[str] = mapped_column(String, default="card", server_default="card")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
