"""Direct payments: customers pay shops via UPI or cash (Razorpay removed)

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-03

- shops: upi_id, upi_qr_url, accepts_upi, accepts_cash
- payments: provider_ref nullable; payer_reference, marked_paid_at, paid_at;
  legacy statuses converted ("succeeded" -> "paid", method "card" kept as-is)
- return_requests: difference_method, difference_payer_reference;
  difference_razorpay_order_id dropped
- platform_settings.payment_gateways: Razorpay entry removed
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

NEW_GATEWAYS = [
    {"key": "upi_direct", "name": "UPI (direct to shop)", "enabled": True, "primary": True},
    {"key": "cod", "name": "Cash on delivery / pickup", "enabled": True, "primary": False},
]


def upgrade() -> None:
    op.add_column("shops", sa.Column("upi_id", sa.String(), nullable=True))
    op.add_column("shops", sa.Column("upi_qr_url", sa.String(), nullable=True))
    op.add_column(
        "shops", sa.Column("accepts_upi", sa.Boolean(), nullable=False, server_default="true")
    )
    op.add_column(
        "shops", sa.Column("accepts_cash", sa.Boolean(), nullable=False, server_default="true")
    )

    op.alter_column("payments", "provider_ref", existing_type=sa.String(), nullable=True)
    op.add_column("payments", sa.Column("payer_reference", sa.String(), nullable=True))
    op.add_column(
        "payments", sa.Column("marked_paid_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("payments", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("payments", "status", existing_type=sa.String(), server_default="unpaid")
    op.alter_column("payments", "method", existing_type=sa.String(), server_default="upi")
    # Old Razorpay payments that cleared are simply "paid" now.
    op.execute("UPDATE payments SET status = 'paid', paid_at = created_at WHERE status = 'succeeded'")

    op.add_column("return_requests", sa.Column("difference_method", sa.String(), nullable=True))
    op.add_column(
        "return_requests", sa.Column("difference_payer_reference", sa.String(), nullable=True)
    )
    op.drop_column("return_requests", "difference_razorpay_order_id")

    op.execute(
        sa.text("UPDATE platform_settings SET payment_gateways = CAST(:g AS JSONB)").bindparams(
            g=json.dumps(NEW_GATEWAYS)
        )
    )


def downgrade() -> None:
    op.add_column(
        "return_requests", sa.Column("difference_razorpay_order_id", sa.String(), nullable=True)
    )
    op.drop_column("return_requests", "difference_payer_reference")
    op.drop_column("return_requests", "difference_method")

    op.execute("UPDATE payments SET status = 'succeeded' WHERE status = 'paid'")
    op.execute("UPDATE payments SET provider_ref = 'none' WHERE provider_ref IS NULL")
    op.alter_column("payments", "method", existing_type=sa.String(), server_default="card")
    op.alter_column("payments", "status", existing_type=sa.String(), server_default="pending")
    op.drop_column("payments", "paid_at")
    op.drop_column("payments", "marked_paid_at")
    op.drop_column("payments", "payer_reference")
    op.alter_column("payments", "provider_ref", existing_type=sa.String(), nullable=False)

    op.drop_column("shops", "accepts_cash")
    op.drop_column("shops", "accepts_upi")
    op.drop_column("shops", "upi_qr_url")
    op.drop_column("shops", "upi_id")
