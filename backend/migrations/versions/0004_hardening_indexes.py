"""Phase 7 hardening pass: missing FK + hot-path indexes

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-02

Confirms/adds indexes per the roadmap's Phase 7 "don't skip": every
foreign key, and every column used in a WHERE/ORDER BY on a hot path.
See the matching comments in app/models/*.py for why each one exists.
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Missing FK indexes
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])
    op.create_index("ix_shops_address_id", "shops", ["address_id"])

    # Hot WHERE columns
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_profiles_role", "profiles", ["role"])

    # Hot ORDER BY column
    op.create_index("ix_products_created_at", "products", ["created_at"])

    # Composite: WHERE is_active ORDER BY rating (GET /shops's hottest query)
    op.create_index("ix_shops_is_active_rating", "shops", ["is_active", "rating"])

    # Composite: WHERE user_id/shop_id = X ORDER BY created_at DESC
    # (order history + Shop Dashboard's order list) — replaces the
    # single-column indexes on orders.user_id / orders.shop_id, since a
    # composite index's leftmost column already serves plain equality
    # lookups on that column just as well.
    op.drop_index("ix_orders_user_id", table_name="orders")
    op.drop_index("ix_orders_shop_id", table_name="orders")
    op.create_index("ix_orders_user_id_created_at", "orders", ["user_id", "created_at"])
    op.create_index("ix_orders_shop_id_created_at", "orders", ["shop_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_orders_shop_id_created_at", table_name="orders")
    op.drop_index("ix_orders_user_id_created_at", table_name="orders")
    op.create_index("ix_orders_shop_id", "orders", ["shop_id"])
    op.create_index("ix_orders_user_id", "orders", ["user_id"])

    op.drop_index("ix_shops_is_active_rating", table_name="shops")
    op.drop_index("ix_products_created_at", table_name="products")
    op.drop_index("ix_profiles_role", table_name="profiles")
    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_shops_address_id", table_name="shops")
    op.drop_index("ix_order_items_product_id", table_name="order_items")
