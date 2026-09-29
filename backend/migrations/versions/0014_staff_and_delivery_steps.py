"""Staff accounts (manager/delivery) + granular delivery status steps

Revision ID: 0014
Revises: 0013
Create Date: 2026-09-26

Two independent additions, shipped together:

1. Staff accounts: shop owners can now create manager/delivery logins
   for their own shop. `profiles.shop_id` records which shop a staff
   member (role="manager" or "delivery") belongs to — see
   app/models/profile.py and routers/shop_dashboard.py's /dashboard/staff
   endpoints. Null for every non-staff profile; a shop_owner's shops are
   still found via Shop.owner_id, never through this column.

2. Delivery pipeline granularity: the old 3-step
   confirmed -> preparing -> ready -> delivered flow becomes
   confirmed -> preparing -> packing -> out_for_delivery -> delivered
   (see app/core/order_status.py). Existing orders sitting at "ready"
   are renamed to "packing" so they land inside the new flow rather than
   being stuck in a status nothing transitions out of anymore.
   `orders.delivery_proof_photo_url` is new: the delivery person's proof
   photo required to mark an order "delivered".
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column(
            "shop_id",
            UUID(as_uuid=True),
            sa.ForeignKey("shops.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_profiles_shop_id", "profiles", ["shop_id"])

    op.add_column("orders", sa.Column("delivery_proof_photo_url", sa.String(), nullable=True))

    # Data migration, not just a schema change: an order sitting at the
    # old "ready" status (one step from delivered under the 3-step flow)
    # needs to land somewhere valid in the new 4-step flow. "packing" is
    # the closest equivalent — "already being prepared, not yet out the
    # door" — rather than silently jumping it straight to
    # "out_for_delivery" or "delivered", which would overstate progress
    # nobody actually confirmed.
    op.execute("UPDATE orders SET status = 'packing' WHERE status = 'ready'")


def downgrade() -> None:
    op.execute("UPDATE orders SET status = 'ready' WHERE status IN ('packing', 'out_for_delivery')")
    op.drop_column("orders", "delivery_proof_photo_url")
    op.drop_index("ix_profiles_shop_id", table_name="profiles")
    op.drop_column("profiles", "shop_id")
