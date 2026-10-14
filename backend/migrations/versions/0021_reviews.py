"""Product and shop reviews

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-14

Adds `product_reviews` and `shop_reviews` (1-5 star rating, optional
title/body, the shop's public reply, and owner hide/unhide fields), plus
the stored aggregates the listing pages read: `products.rating_avg` /
`products.rating_count` and `shops.rating_count` (`shops.rating` already
exists and becomes the shop-review average). See app/models/review.py and
app/core/reviews.py.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def _shared_columns() -> list[sa.Column]:
    return [
        sa.Column("rating", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("body", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reply_text", sa.String(), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replied_by", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hidden_reason", sa.String(), nullable=True),
        sa.Column("hidden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hidden_by", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
    ]


def upgrade() -> None:
    op.add_column("products", sa.Column("rating_avg", sa.Float(), nullable=False, server_default="0"))
    op.add_column("products", sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("shops", sa.Column("rating_count", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "product_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        *_shared_columns(),
        sa.UniqueConstraint("user_id", "product_id", name="uq_product_review_user_product"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_product_review_rating"),
    )
    op.create_index("ix_product_reviews_user_id", "product_reviews", ["user_id"])
    op.create_index("ix_product_reviews_product_id_created_at", "product_reviews", ["product_id", "created_at"])
    op.create_index("ix_product_reviews_shop_id_created_at", "product_reviews", ["shop_id", "created_at"])

    op.create_table(
        "shop_reviews",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        *_shared_columns(),
        sa.UniqueConstraint("user_id", "shop_id", name="uq_shop_review_user_shop"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_shop_review_rating"),
    )
    op.create_index("ix_shop_reviews_user_id", "shop_reviews", ["user_id"])
    op.create_index("ix_shop_reviews_shop_id_created_at", "shop_reviews", ["shop_id", "created_at"])


def downgrade() -> None:
    op.drop_table("shop_reviews")
    op.drop_table("product_reviews")
    op.drop_column("shops", "rating_count")
    op.drop_column("products", "rating_count")
    op.drop_column("products", "rating_avg")
