"""Self-serve sponsorship: plans + purchases

Revision ID: 0019
Revises: 0018

Shop owners buy a plan themselves from the Shop Dashboard; a verified
payment starts the sponsorship automatically (see routers/sponsorship.py).
Seeds three placeholder plans — change the prices in Admin -> Settings.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    plans = op.create_table(
        "sponsorship_plans",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.bulk_insert(
        plans,
        [
            {"key": "week", "name": "1 week", "days": 7, "price": 199, "is_active": True, "sort_order": 1},
            {"key": "month", "name": "1 month", "days": 30, "price": 599, "is_active": True, "sort_order": 2},
            {"key": "quarter", "name": "3 months", "days": 90, "price": 1499, "is_active": True, "sort_order": 3},
        ],
    )
    op.create_table(
        "sponsorship_purchases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purchased_by", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("plan_key", sa.String(), nullable=False),
        sa.Column("plan_name", sa.String(), nullable=False),
        sa.Column("days", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="created"),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("provider_order_id", sa.String(), nullable=True),
        sa.Column("provider_payment_id", sa.String(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sponsorship_purchases_shop_id", "sponsorship_purchases", ["shop_id"])
    op.create_index("ix_sponsorship_purchases_status", "sponsorship_purchases", ["status"])
    op.create_index("ix_sponsorship_purchases_provider_order_id", "sponsorship_purchases", ["provider_order_id"])


def downgrade() -> None:
    op.drop_table("sponsorship_purchases")
    op.drop_table("sponsorship_plans")
