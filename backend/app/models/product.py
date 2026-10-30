import uuid
from datetime import datetime

from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Product(Base):
    """
    `attributes` (JSONB) is the "NoSQL inside Postgres" piece from the
    build guide: a t-shirt can have {"size": "M", "color": "blue"} and a
    bag of rice can have {"weight_kg": 5} without needing a separate table
    per category or a second database.
    """

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    # Maximum Retail Price printed on the pack (optional). `price` above is
    # always what the customer pays; MRP only drives the "X% off" display and
    # must be >= price (DB check + API validation).
    mrp: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Pack size, e.g. 500 + "g", 1 + "l", 6 + "pcs" (both set or both empty).
    unit_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    # The shop's own stock code, and the pack's barcode (EAN/UPC). Each is
    # unique within a shop (partial unique indexes in migration 0026).
    sku: Mapped[str | None] = mapped_column(String, nullable=True)
    barcode: Mapped[str | None] = mapped_column(String, nullable=True)
    # Alert the owner when stock falls to this many. NULL = use the shop's default.
    low_stock_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # What the owner was last alerted about: NULL (fine) | "low" | "out".
    # Makes alerts fire once per drop, not once per sale (core/stock_alerts.py).
    low_stock_state: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String, index=True)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # GST: prices EXCLUDE tax; this percent is added on top at checkout.
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    hsn_code: Mapped[str | None] = mapped_column(String, nullable=True)

    attributes: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    images: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    # See migration 0011's docstring for why this is a shared tag rather
    # than a separate variants table. NULL = standalone product (the
    # common case, and everything that existed before this column).
    variant_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    variant_attributes: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # Stored aggregates over the product's visible (non-hidden) reviews —
    # recomputed in the same transaction as every review change (see
    # app/core/reviews.py) so listings never need a JOIN/AVG per row.
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    rating_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # index=True (Phase 7 hardening pass): shop_dashboard.py's product
    # list orders by this column (`ORDER BY Product.created_at DESC`)
    # for every shop owner, every time they open their dashboard.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    @property
    def unit_label(self) -> str | None:
        from app.core.product_pricing import unit_label

        return unit_label(self.unit_value, self.unit)

    @property
    def discount_percent(self) -> int | None:
        from app.core.product_pricing import discount_percent

        return discount_percent(self.mrp, self.price)

    @property
    def unit_price_label(self) -> str | None:
        from app.core.product_pricing import unit_price_label

        return unit_price_label(self.price, self.unit_value, self.unit)
