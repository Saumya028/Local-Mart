from datetime import datetime

from sqlalchemy import DateTime, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PlatformSettings(Base):
    """
    Deliberately a SINGLETON table: exactly one row (id=1), never more.
    Backs the Admin Panel's Settings page — platform-wide knobs like
    commission % and delivery payout that apply to every shop/order,
    not something scoped per-shop or per-user. A single row read/updated
    in place is simpler and safer here than a key-value table, since the
    full set of fields is small, fixed, and known in advance.
    """

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)

    commission_pct: Mapped[float] = mapped_column(Numeric(5, 2), default=8, server_default="8")
    delivery_payout: Mapped[float] = mapped_column(Numeric(10, 2), default=40, server_default="40")
    min_order_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=99, server_default="99")
    max_delivery_radius_km: Mapped[float] = mapped_column(Numeric(5, 2), default=5, server_default="5")

    # [{"key": "razorpay", "name": "Razorpay", "enabled": true, "primary": true}, ...]
    # A small, fixed list of gateways is genuinely just config, not
    # something with its own lifecycle/relations that would justify a
    # separate table.
    payment_gateways: Mapped[list] = mapped_column(JSONB, default=list)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
