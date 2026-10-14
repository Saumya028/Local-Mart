import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class _ReviewColumns:
    """
    Columns shared by ProductReview and ShopReview. Kept as a plain mixin
    (not a mapped base) so each table stays explicit and flat — the two
    review kinds differ only in WHAT they target, never in how they're
    written, replied to, or moderated.

    Only customers with a delivered/picked-up order can write one (see
    app/core/reviews.py), so every review is a "verified purchase".
    """

    rating: Mapped[int] = mapped_column(SmallInteger)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Set only when the reviewer changes their review after posting it.
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- The shop's public reply (one per review; editable) ---
    reply_text: Mapped[str | None] = mapped_column(String, nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replied_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    # --- Owner moderation ---
    # A hidden review disappears from the public list AND from the
    # product/shop average. The reason/time/actor are kept on the row
    # itself so the hide is always traceable (and an admin can restore it).
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    hidden_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hidden_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )


class ProductReview(_ReviewColumns, Base):
    __tablename__ = "product_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE")
    )
    # Denormalized from the product, same reasoning as
    # ReturnRequest.shop_id: the shop dashboard filters on it every load.
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE")
    )

    __table_args__ = (
        # One review per customer per product (they can edit it). Many
        # different customers can review the same product.
        UniqueConstraint("user_id", "product_id", name="uq_product_review_user_product"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_product_review_rating"),
        Index("ix_product_reviews_product_id_created_at", "product_id", "created_at"),
        Index("ix_product_reviews_shop_id_created_at", "shop_id", "created_at"),
    )


class ShopReview(_ReviewColumns, Base):
    __tablename__ = "shop_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    shop_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="CASCADE")
    )

    __table_args__ = (
        UniqueConstraint("user_id", "shop_id", name="uq_shop_review_user_shop"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_shop_review_rating"),
        Index("ix_shop_reviews_shop_id_created_at", "shop_id", "created_at"),
    )
