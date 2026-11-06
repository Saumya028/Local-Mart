"""Delivery coordinates on orders

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-05

orders.delivery_lat / delivery_lng   the customer's address coordinates,
                                     frozen at checkout, so the shop and the
                                     delivery person can open the drop-off
                                     point in a maps app. Nullable: pickup
                                     orders, addresses saved without a
                                     location, and orders placed before this
                                     migration have none (the UI falls back
                                     to searching the address text).
"""
import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("delivery_lat", sa.Float(), nullable=True))
    op.add_column("orders", sa.Column("delivery_lng", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "delivery_lng")
    op.drop_column("orders", "delivery_lat")
