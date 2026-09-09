"""My Account page: profile phone number + wishlist

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("phone", sa.String(), nullable=True))

    op.create_table(
        "wishlist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),
    )
    op.create_index(
        "ix_wishlist_items_user_id_created_at", "wishlist_items", ["user_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_wishlist_items_user_id_created_at", table_name="wishlist_items")
    op.drop_table("wishlist_items")
    op.drop_column("profiles", "phone")
