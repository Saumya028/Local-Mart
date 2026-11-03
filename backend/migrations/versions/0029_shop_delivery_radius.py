"""Per-shop delivery radius

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-03

shops.delivery_radius_km   how far (km, straight line) this shop delivers.
                           Default 5 = the platform's old fixed radius, so every
                           existing shop behaves exactly as before until its
                           owner changes it.
"""
import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shops",
        sa.Column("delivery_radius_km", sa.Numeric(5, 2), nullable=False, server_default="5"),
    )
    op.create_check_constraint("ck_shops_delivery_radius", "shops", "delivery_radius_km > 0")


def downgrade() -> None:
    op.drop_constraint("ck_shops_delivery_radius", "shops", type_="check")
    op.drop_column("shops", "delivery_radius_km")
