"""Login page: phone-only accounts (profiles.email nullable)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-09

The new Login page's Phone tab authenticates via Supabase phone OTP,
which creates an identity with no email at all. profiles.email was
NOT NULL, which would break profile auto-provisioning (see
security.py's get_current_user) the first time a phone-only user hit
any endpoint. Postgres's UNIQUE constraint on profiles.email is
unaffected by this — it already treats every NULL as distinct from
every other NULL, so any number of phone-only profiles can coexist.
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("profiles", "email", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    # Guard against any phone-only rows that exist by the time this runs
    # "backward" — NOT NULL can't be restored while they exist, so this
    # intentionally fails loudly rather than silently deleting accounts.
    op.execute("UPDATE profiles SET email = 'unknown-' || id || '@example.invalid' WHERE email IS NULL")
    op.alter_column("profiles", "email", existing_type=sa.String(), nullable=False)
