import uuid

from sqlalchemy import ForeignKey, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT")
    )

    quantity: Mapped[int] = mapped_column(Integer)

    # Snapshotted at checkout time, deliberately — if the shop changes the
    # product's price tomorrow, this row still shows what the customer
    # actually paid, which is what an order history or invoice needs.
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))
