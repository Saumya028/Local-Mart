"""Shop verification documents + rejection reason

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-07

Fixes a real gap found in testing: shop applications could be created
and fully operated (products, etc.) with zero verification and no
admin gate actually blocking use. This migration adds the storage for
the fix — routers/shops.py now REQUIRES at least one document to apply,
and shop_dashboard.py now blocks product/order management until
approval_status == "approved" (see that router's `_require_approved`).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "shops",
        sa.Column("documents", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "shops",
        sa.Column("rejection_reason", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shops", "rejection_reason")
    op.drop_column("shops", "documents")
