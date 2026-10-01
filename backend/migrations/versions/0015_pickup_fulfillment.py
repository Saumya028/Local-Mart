"""Pickup fulfillment: shops.pickup_enabled + orders.fulfillment_type

Revision ID: 0015
Revises: 0014
Create Date: 2026-09-29

Adds "Pick up from the shop" as a second fulfillment option alongside
delivery:

- `shops.pickup_enabled` (default true): an owner-toggleable switch —
  see the Shop Dashboard sidebar — for whether this shop offers pickup
  at all. Every existing shop keeps offering it by default unless its
  owner turns it off.
- `orders.fulfillment_type` (default "delivery"): set once at checkout,
  decides which of app/core/order_status.py's two transition maps
  (delivery: ...->out_for_delivery->delivered, pickup:
  ...->ready_for_pickup->picked_up) an order follows. Every existing
  order gets "delivery", which is exactly what it always was.
- `orders.delivery_address` becomes nullable: a pickup order has no
  delivery address at all (see routers/orders.py's checkout) — this was
  NOT NULL before pickup existed, since every order was a delivery.
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shops",
        sa.Column("pickup_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "orders",
        sa.Column("fulfillment_type", sa.String(), nullable=False, server_default="delivery"),
    )
    op.alter_column("orders", "delivery_address", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Any pickup order's delivery_address is NULL by design (see above) —
    # give it a placeholder rather than leaving a NOT NULL column with
    # nulls in it, which downgrade would otherwise be unable to enforce.
    op.execute("UPDATE orders SET delivery_address = 'N/A (picked up)' WHERE delivery_address IS NULL")
    op.alter_column("orders", "delivery_address", existing_type=sa.String(), nullable=False)
    op.drop_column("orders", "fulfillment_type")
    op.drop_column("shops", "pickup_enabled")
