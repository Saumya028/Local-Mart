"""Paid promotional banners: slots, banners, banner payments, banner radius

Revision ID: 0020
Revises: 0019

Shops request a banner for a pre-decided slot, an admin approves it, the
owner pays, and it runs for the slot's duration — shown only to customers
within platform_settings.banner_radius_km of the shop. Seeds four
placeholder slots; change prices in Admin -> Settings.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column("banner_radius_km", sa.Numeric(5, 2), nullable=False, server_default="1"),
    )

    slots = op.create_table(
        "banner_slots",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.bulk_insert(
        slots,
        [
            {"key": "home_top", "name": "Home page - top banner", "width": 1200, "height": 300, "price": 1999,
             "description": "Large banner right under the search box on the landing page.", "sort_order": 1},
            {"key": "home_middle", "name": "Home page - middle banner", "width": 1200, "height": 250, "price": 1299,
             "description": "Between the featured stores and popular products on the landing page.", "sort_order": 2},
            {"key": "search_top", "name": "Search results - top banner", "width": 1200, "height": 200, "price": 999,
             "description": "Above the product results on the search page.", "sort_order": 3},
            {"key": "stores_top", "name": "Stores page - top banner", "width": 1200, "height": 200, "price": 799,
             "description": "Above the shop list on the stores page.", "sort_order": 4},
        ],
    )

    op.create_table(
        "banners",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slot_key", sa.String(), sa.ForeignKey("banner_slots.key"), nullable=False),
        sa.Column("image_url", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("review_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.String(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_banners_shop_id", "banners", ["shop_id"])
    op.create_index("ix_banners_slot_key", "banners", ["slot_key"])
    op.create_index("ix_banners_review_status", "banners", ["review_status"])
    op.create_index("ix_banners_ends_at", "banners", ["ends_at"])

    op.create_table(
        "banner_payments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("banner_id", UUID(as_uuid=True), sa.ForeignKey("banners.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purchased_by", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
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
    op.create_index("ix_banner_payments_banner_id", "banner_payments", ["banner_id"])
    op.create_index("ix_banner_payments_status", "banner_payments", ["status"])
    op.create_index("ix_banner_payments_provider_order_id", "banner_payments", ["provider_order_id"])


def downgrade() -> None:
    op.drop_table("banner_payments")
    op.drop_table("banners")
    op.drop_table("banner_slots")
    op.drop_column("platform_settings", "banner_radius_km")
