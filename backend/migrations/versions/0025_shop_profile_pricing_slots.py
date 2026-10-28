"""Shop profile (hours, vacation, phone), delivery pricing, ETA & slots

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-26

shops:  contact_phone, description, opening_hours, timezone, temporarily_closed,
        closed_until, closed_message, delivery_fee, free_delivery_above,
        min_order_amount, prep/delivery minutes, slot settings
orders: subtotal_amount, delivery_fee, eta_at, slot_start, slot_end

Existing rows: shops get "no hours set" (= always open), fee 0, no minimum, no
slots — i.e. behave exactly as before. Existing orders get subtotal = total,
fee 0.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("shops", sa.Column("contact_phone", sa.String(), nullable=True))
    op.add_column("shops", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("shops", sa.Column("opening_hours", JSONB(), nullable=True))
    op.add_column("shops", sa.Column("timezone", sa.String(), nullable=False, server_default="Asia/Kolkata"))
    op.add_column("shops", sa.Column("temporarily_closed", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("shops", sa.Column("closed_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shops", sa.Column("closed_message", sa.String(), nullable=True))
    op.add_column("shops", sa.Column("delivery_fee", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("shops", sa.Column("free_delivery_above", sa.Numeric(10, 2), nullable=True))
    op.add_column("shops", sa.Column("min_order_amount", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("shops", sa.Column("prep_time_minutes", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("shops", sa.Column("delivery_time_minutes", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("shops", sa.Column("slots_enabled", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("shops", sa.Column("slot_length_minutes", sa.Integer(), nullable=False, server_default="60"))
    op.add_column("shops", sa.Column("slot_capacity", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("shops", sa.Column("slot_days_ahead", sa.Integer(), nullable=False, server_default="2"))

    # Defence in depth: the API validates these, the database refuses nonsense too.
    op.create_check_constraint("ck_shops_delivery_fee", "shops", "delivery_fee >= 0")
    op.create_check_constraint("ck_shops_min_order", "shops", "min_order_amount >= 0")
    op.create_check_constraint("ck_shops_free_above", "shops", "free_delivery_above IS NULL OR free_delivery_above >= 0")
    op.create_check_constraint("ck_shops_slot_capacity", "shops", "slot_capacity >= 1")
    op.create_check_constraint("ck_shops_slot_length", "shops", "slot_length_minutes >= 15")

    op.add_column("orders", sa.Column("subtotal_amount", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("delivery_fee", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("orders", sa.Column("eta_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("slot_start", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("slot_end", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE orders SET subtotal_amount = total_amount")
    # Counting a slot's bookings is on the checkout hot path.
    op.execute(
        "CREATE INDEX ix_orders_shop_slot ON orders (shop_id, slot_start) WHERE slot_start IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_orders_shop_slot")
    for col in ("slot_end", "slot_start", "eta_at", "delivery_fee", "subtotal_amount"):
        op.drop_column("orders", col)
    for name in ("ck_shops_slot_length", "ck_shops_slot_capacity", "ck_shops_free_above", "ck_shops_min_order", "ck_shops_delivery_fee"):
        op.drop_constraint(name, "shops", type_="check")
    for col in (
        "slot_days_ahead", "slot_capacity", "slot_length_minutes", "slots_enabled", "delivery_time_minutes",
        "prep_time_minutes", "min_order_amount", "free_delivery_above", "delivery_fee", "closed_message",
        "closed_until", "temporarily_closed", "timezone", "opening_hours", "description", "contact_phone",
    ):
        op.drop_column("shops", col)
