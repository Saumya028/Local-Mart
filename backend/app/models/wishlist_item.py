import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class WishlistItem(Base):
    """
    One row per (user, product) a customer has saved for later — backs
    the My Account page's Wishlist tab and its count on the profile
    card. Deliberately just a join table, not a richer "list" concept
    (named lists, notes, etc.) — nothing in the product needs more than
    a single flat "saved for later" set per user yet.
    """

    __tablename__ = "wishlist_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE")
    )
    # CASCADE: if a product is ever hard-deleted, it should just quietly
    # disappear from everyone's wishlist rather than leave a dangling
    # reference the frontend has to defensively handle. (Shops/owners
    # normally deactivate products via is_active rather than deleting
    # them — this is a safety net for the rare hard-delete case.)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE")
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # A product can only be wishlisted once per user — POST /wishlist
        # relies on this to make adding an already-wishlisted product a
        # harmless no-op rather than a growing pile of duplicate rows.
        UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),
        # GET /wishlist's whole query is "WHERE user_id = X ORDER BY
        # created_at DESC" — same composite-index reasoning as orders.
        Index("ix_wishlist_items_user_id_created_at", "user_id", "created_at"),
    )
