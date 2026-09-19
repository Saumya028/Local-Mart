"""Shop address + geolocation (5km radius filtering)

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-19

Shops had no address or coordinates at all — the "Apply to sell" form
only ever collected name/category/documents. That made it impossible to
show a shop's location or filter shops by distance, which is the actual
"local" in LocalMart. Adds address_line1/city (free text, shown on the
storefront) and latitude/longitude (captured via the browser's
Geolocation API on the apply form) to shops directly, rather than
reusing the existing addresses table — that table's semantics are a
customer's *delivery* address (see Address model), and a shop isn't
owned by a "user_id" in that sense. shops.address_id remains unused
dead weight from an earlier design; left alone here since dropping it
is a separate, unrelated cleanup.

Nullable, so existing/seed shops don't break — GET /shops's distance
filter simply excludes any shop with no coordinates on file (see
routers/shops.py) rather than erroring on it. New applications require
all four fields (see ShopCreate's validators).
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shops", sa.Column("address_line1", sa.String(), nullable=True))
    op.add_column("shops", sa.Column("city", sa.String(), nullable=True))
    op.add_column("shops", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("shops", sa.Column("longitude", sa.Float(), nullable=True))
    # Distance filtering (GET /shops?lat=...&lng=...) scans exactly this
    # pair — index them together so Postgres isn't doing a full table scan
    # once shop counts grow past what fits comfortably in memory.
    op.create_index("ix_shops_lat_lng", "shops", ["latitude", "longitude"])


def downgrade() -> None:
    op.drop_index("ix_shops_lat_lng", table_name="shops")
    op.drop_column("shops", "longitude")
    op.drop_column("shops", "latitude")
    op.drop_column("shops", "city")
    op.drop_column("shops", "address_line1")
