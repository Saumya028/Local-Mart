import uuid

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    # index=True (Phase 7 hardening pass): every foreign key should have
    # one, and this specific column is also joined against directly in
    # orders.py's get_order (OrderItem.product_id == Product.id).
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )

    quantity: Mapped[int] = mapped_column(Integer)

    # Snapshotted at checkout time, deliberately — if the shop changes the
    # product's price tomorrow, this row still shows what the customer
    # actually paid, which is what an order history or invoice needs.
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))
    # Snapshots of what the customer saw when they ordered, so editing the
    # product later can't rewrite history (savings shown, pack size).
    mrp: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit_label: Mapped[str | None] = mapped_column(String, nullable=True)
    # GST snapshot (percent) and HSN code at checkout.
    gst_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    hsn_code: Mapped[str | None] = mapped_column(String, nullable=True)
