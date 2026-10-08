"""Sponsored (paid-priority) shops: shops.sponsored_until

Revision ID: 0018
Revises: 0017

A shop that has paid the platform's promotion fee is shown ABOVE
non-paying shops in product search and shop listings, until this
timestamp passes. NULL (the default) or a past time = not sponsored, so
every existing shop is unchanged and sponsorship expires on its own with
no cleanup job. An admin sets it (see routers/admin.py's
set_shop_sponsorship) after receiving payment.
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shops", sa.Column("sponsored_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_shops_sponsored_until", "shops", ["sponsored_until"])


def downgrade() -> None:
    op.drop_index("ix_shops_sponsored_until", table_name="shops")
    op.drop_column("shops", "sponsored_until")
