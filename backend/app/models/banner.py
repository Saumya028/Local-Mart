import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class BannerSlot(Base):
    """A pre-decided place on the site where a shop can buy a banner (e.g.
    "Home page — top banner"). Admin controls price / availability; the
    pixel size is fixed by the page layout, so it is seeded, not edited."""

    __tablename__ = "banner_slots"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String, default="", server_default="")
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    duration_days: Mapped[int] = mapped_column(Integer, default=30, server_default="30")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Banner(Base):
    """One shop's banner request for one slot.

    Lifecycle: pending (awaiting admin review) -> approved (owner can now
    pay) -> live for `duration_days` once paid -> expired (renew to run
    again). Or rejected (with a reason). `state` below derives the label.
    A banner is shown to customers only while it is approved AND
    ends_at is in the future, and only to viewers within the platform's
    banner radius of the shop."""

    __tablename__ = "banners"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )
    slot_key: Mapped[str] = mapped_column(String, ForeignKey("banner_slots.key"), index=True)
    image_url: Mapped[str] = mapped_column(String)
    title: Mapped[str | None] = mapped_column(String, nullable=True)

    review_status: Mapped[str] = mapped_column(String, default="pending", server_default="pending", index=True)
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Paid window. NULL until the first payment lands.
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    impressions: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    clicks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def state(self) -> str:
        if self.review_status in ("pending", "rejected"):
            return self.review_status
        if self.ends_at is None:
            return "awaiting_payment"
        return "live" if self.ends_at > datetime.now(timezone.utc) else "expired"


class BannerPayment(Base):
    """One payment (initial or renewal) for a banner. Same shape as
    SponsorshipPurchase; only status="paid" rows extend Banner.ends_at."""

    __tablename__ = "banner_payments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    banner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("banners.id", ondelete="CASCADE"), index=True
    )
    purchased_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    days: Mapped[int] = mapped_column(Integer)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String, default="created", server_default="created", index=True)
    provider: Mapped[str] = mapped_column(String)
    provider_order_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String, nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
