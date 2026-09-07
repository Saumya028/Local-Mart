"""Admin dashboard redesign: shop approval workflow, user suspension, platform settings

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-05

Backs the new Admin Panel (Dashboard / Manage Shops / Manage Users /
Reports / Settings): shops gain an approval + docs-verification
workflow, profiles gain a suspend flag, and a new singleton
platform_settings table backs the Settings page.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing shops predate this feature — default them to
    # already-approved/verified so nothing disappears from the public
    # catalog the moment this migration runs. New rows created after this
    # (see app/models/shop.py's `default=`) start "pending"/"pending"
    # instead; that's a Python-side default, not a DB one, so it doesn't
    # affect this backfill.
    op.add_column(
        "shops",
        sa.Column("approval_status", sa.String(), nullable=False, server_default="approved"),
    )
    op.add_column(
        "shops",
        sa.Column("docs_status", sa.String(), nullable=False, server_default="verified"),
    )
    op.create_index("ix_shops_approval_status", "shops", ["approval_status"])

    op.add_column(
        "profiles",
        sa.Column("is_suspended", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("commission_pct", sa.Numeric(5, 2), nullable=False, server_default="8"),
        sa.Column("delivery_payout", sa.Numeric(10, 2), nullable=False, server_default="40"),
        sa.Column("min_order_amount", sa.Numeric(10, 2), nullable=False, server_default="99"),
        sa.Column("max_delivery_radius_km", sa.Numeric(5, 2), nullable=False, server_default="5"),
        sa.Column("payment_gateways", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Seed the single settings row + a sensible default gateway config —
    # matching the mockup: Razorpay primary, UPI Direct and Cash on
    # Delivery both active.
    op.execute(
        """
        INSERT INTO platform_settings (id, commission_pct, delivery_payout, min_order_amount, max_delivery_radius_km, payment_gateways)
        VALUES (
            1, 8, 40, 99, 5,
            '[
                {"key": "razorpay", "name": "Razorpay", "enabled": true, "primary": true},
                {"key": "upi_direct", "name": "UPI Direct", "enabled": true, "primary": false},
                {"key": "cod", "name": "Cash on Delivery", "enabled": true, "primary": false}
            ]'::jsonb
        )
        """
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
    op.drop_column("profiles", "is_suspended")
    op.drop_index("ix_shops_approval_status", table_name="shops")
    op.drop_column("shops", "docs_status")
    op.drop_column("shops", "approval_status")
