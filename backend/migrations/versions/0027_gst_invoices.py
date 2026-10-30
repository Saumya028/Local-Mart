"""GST invoices: shop GSTIN, product GST rate/HSN, order tax + invoice number

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-29

products:    gst_rate (percent, default 0), hsn_code
shops:       gstin, legal_name, invoice_seq (per-shop invoice counter)
orders:      tax_amount, invoice_number, buyer_gstin, buyer_business_name
order_items: gst_rate, hsn_code (snapshots at checkout)

Existing rows keep meaning: 0% GST, no invoice number yet (one is assigned the
first time an invoice is requested).  Prices exclude GST from here on;
orders.total_amount = subtotal_amount + tax_amount + delivery_fee.
"""
import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("gst_rate", sa.Numeric(5, 2), nullable=False, server_default="0"))
    op.add_column("products", sa.Column("hsn_code", sa.String(), nullable=True))
    op.create_check_constraint("ck_products_gst_rate", "products", "gst_rate >= 0 AND gst_rate <= 28")

    op.add_column("shops", sa.Column("gstin", sa.String(15), nullable=True))
    op.add_column("shops", sa.Column("legal_name", sa.String(), nullable=True))
    op.add_column("shops", sa.Column("invoice_seq", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("orders", sa.Column("tax_amount", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("invoice_number", sa.String(), nullable=True))
    op.add_column("orders", sa.Column("buyer_gstin", sa.String(15), nullable=True))
    op.add_column("orders", sa.Column("buyer_business_name", sa.String(), nullable=True))
    op.create_index(
        "ix_orders_shop_invoice_number", "orders", ["shop_id", "invoice_number"], unique=True,
        postgresql_where=sa.text("invoice_number IS NOT NULL"),
    )

    op.add_column("order_items", sa.Column("gst_rate", sa.Numeric(5, 2), nullable=False, server_default="0"))
    op.add_column("order_items", sa.Column("hsn_code", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("order_items", "hsn_code")
    op.drop_column("order_items", "gst_rate")
    op.drop_index("ix_orders_shop_invoice_number", table_name="orders")
    op.drop_column("orders", "buyer_business_name")
    op.drop_column("orders", "buyer_gstin")
    op.drop_column("orders", "invoice_number")
    op.drop_column("orders", "tax_amount")
    op.drop_column("shops", "invoice_seq")
    op.drop_column("shops", "legal_name")
    op.drop_column("shops", "gstin")
    op.drop_constraint("ck_products_gst_rate", "products", type_="check")
    op.drop_column("products", "hsn_code")
    op.drop_column("products", "gst_rate")
