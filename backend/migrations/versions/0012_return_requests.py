"""Return / exchange requests, and orders.delivered_at

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-23

Adds the customer-return / exchange flow: a `return_requests` table (one
row per line item a customer asks to send back or swap), and a
`delivered_at` timestamp on `orders` — the return window in
app/core/return_status.py counts from the moment an order was actually
delivered, not from checkout time, so that timestamp has to exist
somewhere. See app/models/return_request.py and app/core/return_status.py
for the full reasoning behind the shape of this table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "return_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "order_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("order_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("request_type", sa.String(), nullable=False, server_default="return"),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column(
            "exchange_product_id",
            UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("refund_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="requested"),
        sa.Column("shop_note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_return_requests_order_id", "return_requests", ["order_id"])
    op.create_index("ix_return_requests_order_item_id", "return_requests", ["order_item_id"])
    op.create_index("ix_return_requests_user_id", "return_requests", ["user_id"])
    op.create_index("ix_return_requests_shop_id", "return_requests", ["shop_id"])
    op.create_index("ix_return_requests_status", "return_requests", ["status"])
    # Composite indexes for the two list endpoints' actual query shape —
    # "WHERE shop_id/user_id = X ORDER BY created_at DESC" — same reasoning
    # as the equivalent indexes on `orders` in 0004_hardening_indexes.py.
    op.create_index("ix_return_requests_shop_id_created_at", "return_requests", ["shop_id", "created_at"])
    op.create_index("ix_return_requests_user_id_created_at", "return_requests", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_return_requests_user_id_created_at", table_name="return_requests")
    op.drop_index("ix_return_requests_shop_id_created_at", table_name="return_requests")
    op.drop_index("ix_return_requests_status", table_name="return_requests")
    op.drop_index("ix_return_requests_shop_id", table_name="return_requests")
    op.drop_index("ix_return_requests_user_id", table_name="return_requests")
    op.drop_index("ix_return_requests_order_item_id", table_name="return_requests")
    op.drop_index("ix_return_requests_order_id", table_name="return_requests")
    op.drop_table("return_requests")
    op.drop_column("orders", "delivered_at")
