"""Customer details: DOB, gender, business (GST) accounts, richer addresses

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-06

- profiles: date_of_birth, gender, customer_type (individual|business),
  business_name, gstin, pan, gst_verified
- addresses: recipient_name, phone, line2, landmark, state, pincode

Every new column is nullable (or defaulted), so existing accounts and
saved addresses keep working untouched.
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("profiles", sa.Column("gender", sa.String(), nullable=True))
    op.add_column(
        "profiles",
        sa.Column("customer_type", sa.String(), nullable=False, server_default="individual"),
    )
    op.add_column("profiles", sa.Column("business_name", sa.String(), nullable=True))
    op.add_column("profiles", sa.Column("gstin", sa.String(length=15), nullable=True))
    op.add_column("profiles", sa.Column("pan", sa.String(length=10), nullable=True))
    op.add_column(
        "profiles",
        sa.Column("gst_verified", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_profiles_customer_type", "profiles", ["customer_type"])
    op.create_index("ix_profiles_gstin", "profiles", ["gstin"])

    op.add_column("addresses", sa.Column("recipient_name", sa.String(), nullable=True))
    op.add_column("addresses", sa.Column("phone", sa.String(), nullable=True))
    op.add_column("addresses", sa.Column("line2", sa.String(), nullable=True))
    op.add_column("addresses", sa.Column("landmark", sa.String(), nullable=True))
    op.add_column("addresses", sa.Column("state", sa.String(), nullable=True))
    op.add_column("addresses", sa.Column("pincode", sa.String(length=6), nullable=True))


def downgrade() -> None:
    for col in ("pincode", "state", "landmark", "line2", "phone", "recipient_name"):
        op.drop_column("addresses", col)

    op.drop_index("ix_profiles_gstin", table_name="profiles")
    op.drop_index("ix_profiles_customer_type", table_name="profiles")
    for col in (
        "gst_verified",
        "pan",
        "gstin",
        "business_name",
        "customer_type",
        "gender",
        "date_of_birth",
    ):
        op.drop_column("profiles", col)
