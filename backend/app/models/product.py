import uuid
from datetime import datetime

from sqlalchemy import String, Numeric, Integer, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
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
    category: Mapped[str] = mapped_column(String, index=True)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    attributes: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    images: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
