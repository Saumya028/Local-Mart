"""Recommendation engine: model runs, similarities, popularity, events

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-15

Adds the tables behind the nightly-built "customers also bought" model
(see app/core/recommendations and backend/docs/recommendations.md) plus
profiles.personalization_opt_out.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("personalization_opt_out", sa.Boolean(), nullable=False, server_default="false"),
    )

    op.create_table(
        "recommendation_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(), nullable=False, server_default="building"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats", JSONB(), nullable=False, server_default="{}"),
        sa.Column("error", sa.String(), nullable=True),
    )
    op.create_index("ix_recommendation_runs_status", "recommendation_runs", ["status"])
    op.create_index(
        "uq_recommendation_one_active",
        "recommendation_runs",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "product_similarity",
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("recommendation_runs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("kind", sa.String(), primary_key=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("similar_product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("co_buyers", sa.Integer(), nullable=False),
    )
    op.create_index("ix_product_similarity_similar", "product_similarity", ["similar_product_id"])

    op.create_table(
        "product_popularity",
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("recommendation_runs.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("buyers_30d", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "recommendation_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True),
        sa.Column("surface", sa.String(), nullable=False),
        sa.Column("event", sa.String(), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.SmallInteger(), nullable=True),
        sa.Column("run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("variant", sa.String(), nullable=False, server_default="model"),
    )
    op.create_index("ix_recommendation_events_created_at", "recommendation_events", ["created_at"])
    op.create_index(
        "ix_reco_events_surface_event_created", "recommendation_events", ["surface", "event", "created_at"]
    )
    op.create_index(
        "ix_reco_events_user_product_created", "recommendation_events", ["user_id", "product_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_table("recommendation_events")
    op.drop_table("product_popularity")
    op.drop_table("product_similarity")
    op.drop_table("recommendation_runs")
    op.drop_column("profiles", "personalization_opt_out")
