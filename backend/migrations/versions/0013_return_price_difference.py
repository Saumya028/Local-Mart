"""Exchange price-difference settlement on return_requests

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-24

Adds the columns app/models/return_request.py's ReturnRequest already
declares for settling a price difference on an exchange (a customer
swapping into a pricier or cheaper item) and for linking a completed
exchange to the new Order created for the replacement item. See that
model's inline comments for the full reasoning behind each column.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "return_requests",
        sa.Column("price_difference", sa.Numeric(10, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "return_requests", sa.Column("difference_razorpay_order_id", sa.String(), nullable=True)
    )
    op.add_column(
        "return_requests",
        sa.Column("difference_paid", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "return_requests",
        sa.Column(
            "new_order_id",
            UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("return_requests", "new_order_id")
    op.drop_column("return_requests", "difference_paid")
    op.drop_column("return_requests", "difference_razorpay_order_id")
    op.drop_column("return_requests", "price_difference")
