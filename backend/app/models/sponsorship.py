import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SponsorshipPlan(Base):
    """A purchasable promotion length (e.g. 30 days for Rs 599). Admin can
    change prices / switch plans off in Settings; existing purchases keep
    the price and days they were bought at (copied onto the purchase)."""

    __tablename__ = "sponsorship_plans"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    days: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class SponsorshipPurchase(Base):
    """One attempt by a shop owner to buy a plan. status: created -> paid
    (or failed). Only a paid purchase extends Shop.sponsored_until. This
    table is also the admin's record of which shops bought what, when."""

    __tablename__ = "sponsorship_purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    purchased_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    plan_key: Mapped[str] = mapped_column(String)
    plan_name: Mapped[str] = mapped_column(String)
    days: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))

    status: Mapped[str] = mapped_column(String, default="created", server_default="created", index=True)
    # "razorpay" or "test" (no-money local mode)
    provider: Mapped[str] = mapped_column(String)
    provider_order_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # The window this purchase added: starts_at is when it began counting
    # (now, or the end of the previous sponsorship if renewed early).
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
