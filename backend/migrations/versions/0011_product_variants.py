"""Product variants (color/size/weight) via a shared variant_group_id

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-22

Real listings need "Black earphones" and "White earphones", or "250g
jar" and "1kg jar", to be variants of the same underlying product, not
unrelated listings a customer has to find separately.

Deliberately NOT a separate product_variants table with its own
price/stock/images columns — that would require touching cart, orders,
checkout, payments, and stock-decrement logic everywhere they reference
a product, since none of those know anything but a plain product_id
today. Instead, each variant stays a completely normal, independent
`products` row (own price, stock, images, attributes — everything
already works unchanged: add-to-cart, checkout, order history, stock
decrement, analytics), and `variant_group_id` is just a shared tag that
says "these rows are the same underlying item, shown together on one
product page." `variant_attributes` (e.g. {"Color": "Black"}) is what
differs about THIS row from its siblings; shared specs (brand, warranty,
etc.) stay in the existing `attributes` column as before.

A product with variant_group_id = NULL is a standalone product exactly
like today — this is fully backward compatible with every product that
already exists.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("variant_group_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("products", sa.Column("variant_attributes", JSONB, nullable=False, server_default="{}"))
    # GET /products/{id} looks up every sibling sharing this group on
    # every product-detail-page load — worth an index even at modest
    # catalog size, same reasoning as every other FK-shaped lookup here.
    op.create_index("ix_products_variant_group_id", "products", ["variant_group_id"])


def downgrade() -> None:
    op.drop_index("ix_products_variant_group_id", table_name="products")
    op.drop_column("products", "variant_attributes")
    op.drop_column("products", "variant_group_id")
