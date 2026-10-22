"""Typo-tolerant, index-backed text search (pg_trgm)

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-21

Search used plain ILIKE '%q%', which can't use a normal btree index and
can't tolerate typos. pg_trgm gives us (a) GIN trigram indexes that make
substring ILIKE fast, and (b) word_similarity() for typo tolerance (used by
routers/products.py).

Supabase: pg_trgm is available on every project. If CREATE EXTENSION is
refused for your role, enable it once in Dashboard -> Database -> Extensions
(search "pg_trgm") and re-run `alembic upgrade head`.
"""
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX IF NOT EXISTS ix_products_name_trgm ON products USING gin (name gin_trgm_ops)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_products_description_trgm "
        "ON products USING gin (description gin_trgm_ops)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_shops_name_trgm ON shops USING gin (name gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_shops_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_products_description_trgm")
    op.execute("DROP INDEX IF EXISTS ix_products_name_trgm")
    # The extension is left installed: other objects may rely on it.
