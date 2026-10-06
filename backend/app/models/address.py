import uuid
from datetime import datetime

from sqlalchemy import String, Float, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )

    label: Mapped[str] = mapped_column(String)          # e.g. "Home", "Work"
    # Who receives the parcel and how the delivery partner reaches them —
    # may differ from the account holder (e.g. a gift). Nullable only
    # because addresses saved before these columns existed don't have them.
    recipient_name: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    line1: Mapped[str] = mapped_column(String)
    line2: Mapped[str | None] = mapped_column(String, nullable=True)
    landmark: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str] = mapped_column(String)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(6), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def snapshot(self) -> str:
        """
        One-line text copy of this address, frozen onto an order at
        checkout (orders.delivery_address) so later edits/deletes of the
        saved address never rewrite an old order. Includes the recipient
        and phone because the delivery partner reads exactly this string.
        """
        street = ", ".join(p for p in (self.line1, self.line2, self.landmark) if p)
        place = ", ".join(p for p in (self.city, self.state) if p)
        if self.pincode:
            place = f"{place} - {self.pincode}" if place else self.pincode
        who = ", ".join(p for p in (self.recipient_name, self.phone) if p)
        parts = [p for p in (who, street, place) if p]
        return f"{self.label}: " + ", ".join(parts)
