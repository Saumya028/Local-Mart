"""Product MRP, pack size, SKU, barcode, low-stock alerts

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-28

products:    mrp, unit_value, unit, sku, barcode, low_stock_threshold, low_stock_state
shops:       low_stock_threshold (default 5)
order_items: mrp, unit_label (snapshots)

Existing rows are untouched in meaning: no MRP (no discount shown), no pack
size, no SKU/barcode, shop default threshold 5.

The stock check is added NOT VALID: it applies to every new write but doesn't
fail the migration if an old row is already negative (possible before cart
quantities were validated).
"""
import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("mrp", sa.Numeric(10, 2), nullable=True))
    op.add_column("products", sa.Column("unit_value", sa.Numeric(10, 3), nullable=True))
    op.add_column("products", sa.Column("unit", sa.String(), nullable=True))
    op.add_column("products", sa.Column("sku", sa.String(), nullable=True))
    op.add_column("products", sa.Column("barcode", sa.String(), nullable=True))
    op.add_column("products", sa.Column("low_stock_threshold", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("low_stock_state", sa.String(), nullable=True))

    op.create_check_constraint("ck_products_mrp_not_below_price", "products", "mrp IS NULL OR mrp >= price")
    op.create_check_constraint("ck_products_unit_pair", "products", "(unit_value IS NULL) = (unit IS NULL)")
    op.create_check_constraint("ck_products_unit_value_positive", "products", "unit_value IS NULL OR unit_value > 0")
    op.execute("ALTER TABLE products ADD CONSTRAINT ck_products_stock_nonneg CHECK (stock_qty >= 0) NOT VALID")

    # Unique within a shop (two shops may both sell the same barcode).
    op.execute("CREATE UNIQUE INDEX ix_products_shop_sku ON products (shop_id, lower(sku)) WHERE sku IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX ix_products_shop_barcode ON products (shop_id, barcode) WHERE barcode IS NOT NULL")
    # "Which of my products are low/out?" and scanning a barcode are both common.
    op.execute("CREATE INDEX ix_products_low_stock ON products (shop_id) WHERE low_stock_state IS NOT NULL")

    op.add_column("shops", sa.Column("low_stock_threshold", sa.Integer(), nullable=False, server_default="5"))
    op.create_check_constraint("ck_shops_low_stock_threshold", "shops", "low_stock_threshold >= 0")

    op.add_column("order_items", sa.Column("mrp", sa.Numeric(10, 2), nullable=True))
    op.add_column("order_items", sa.Column("unit_label", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("order_items", "unit_label")
    op.drop_column("order_items", "mrp")
    op.drop_constraint("ck_shops_low_stock_threshold", "shops", type_="check")
    op.drop_column("shops", "low_stock_threshold")
    op.execute("DROP INDEX IF EXISTS ix_products_low_stock")
    op.execute("DROP INDEX IF EXISTS ix_products_shop_barcode")
    op.execute("DROP INDEX IF EXISTS ix_products_shop_sku")
    for name in ("ck_products_stock_nonneg", "ck_products_unit_value_positive", "ck_products_unit_pair", "ck_products_mrp_not_below_price"):
        op.drop_constraint(name, "products", type_="check")
    for col in ("low_stock_state", "low_stock_threshold", "barcode", "sku", "unit", "unit_value", "mrp"):
        op.drop_column("products", col)
