"""Customer support: problem reports, shop disputes, admin resolution

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-30

support_cases         one row per report (order problem, payment problem,
                      shop report, general issue). At most ONE unresolved case
                      per order (partial unique index).
support_case_events   append-only history of each case (UPDATEs are rejected by
                      a trigger, same pattern as order_events).
profiles              support_flagged_at / support_flag_note: admin's "repeat
                      false-dispute" marker (informational only).

Nothing existing changes meaning. Returns (return_requests) are untouched.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def upgrade() -> None:
    op.add_column("profiles", _ts("support_flagged_at", nullable=True))
    op.add_column("profiles", sa.Column("support_flag_note", sa.String(), nullable=True))

    op.create_table(
        "support_cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shop_id", UUID(as_uuid=True), sa.ForeignKey("shops.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("photos", JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("resolution", sa.String(), nullable=True),
        _ts("shop_due_at", nullable=True),
        _ts("overdue_flagged_at", nullable=True),
        sa.Column("info_request_text", sa.Text(), nullable=True),
        _ts("info_requested_at", nullable=True),
        sa.Column("info_reply_text", sa.Text(), nullable=True),
        sa.Column("info_reply_photos", JSONB(), nullable=False, server_default="[]"),
        _ts("info_replied_at", nullable=True),
        sa.Column("shop_response_type", sa.String(), nullable=True),
        sa.Column("shop_response_text", sa.Text(), nullable=True),
        sa.Column("shop_response_photos", JSONB(), nullable=False, server_default="[]"),
        _ts("shop_responded_at", nullable=True),
        sa.Column("shop_responder_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
        _ts("auto_close_at", nullable=True),
        _ts("escalated_at", nullable=True),
        sa.Column("escalation_note", sa.Text(), nullable=True),
        sa.Column("ruling", sa.String(), nullable=True),
        sa.Column("ruling_note", sa.Text(), nullable=True),
        _ts("ruled_at", nullable=True),
        sa.Column("ruled_by", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_action", sa.String(), nullable=True),
        sa.Column("order_action_note", sa.Text(), nullable=True),
        _ts("order_action_deadline", nullable=True),
        _ts("order_action_done_at", nullable=True),
        _ts("action_overdue_flagged_at", nullable=True),
        sa.Column("review_outcome", sa.String(), nullable=True),
        _ts("reviewed_at", nullable=True),
        sa.Column("internal_note", sa.Text(), nullable=True),
        _ts("resolved_at", nullable=True),
        _ts("created_at", nullable=False, server_default=sa.func.now()),
        _ts("updated_at", nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_support_cases_kind", "support_cases", ["kind"])
    op.create_index("ix_support_cases_user_id", "support_cases", ["user_id"])
    op.create_index("ix_support_cases_order_id", "support_cases", ["order_id"])
    op.create_index("ix_support_cases_shop_id", "support_cases", ["shop_id"])
    op.create_index("ix_support_cases_status", "support_cases", ["status"])
    op.create_index("ix_support_cases_shop_status", "support_cases", ["shop_id", "status"])
    op.create_index("ix_support_cases_user_created", "support_cases", ["user_id", "created_at"])
    op.create_index(
        "uq_support_cases_one_open_per_order", "support_cases", ["order_id"], unique=True,
        postgresql_where=sa.text("order_id IS NOT NULL AND status <> 'resolved'"),
    )

    op.create_table(
        "support_case_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", UUID(as_uuid=True), sa.ForeignKey("support_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_role", sa.String(), nullable=False, server_default="system"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("meta", JSONB(), nullable=True),
        _ts("created_at", nullable=False, server_default=sa.func.clock_timestamp()),
    )
    op.create_index("ix_support_case_events_case_id", "support_case_events", ["case_id"])
    op.execute(
        """
        CREATE FUNCTION support_case_events_block_update() RETURNS trigger AS $$
        BEGIN
            -- Only permitted change: actor_id -> NULL (ON DELETE SET NULL when
            -- an account is deleted; actor_role keeps recording who they were).
            IF NEW.actor_id IS NOT NULL
               OR (to_jsonb(NEW) - 'actor_id') IS DISTINCT FROM (to_jsonb(OLD) - 'actor_id') THEN
                RAISE EXCEPTION 'support_case_events is append-only';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER support_case_events_no_update BEFORE UPDATE ON support_case_events
        FOR EACH ROW EXECUTE FUNCTION support_case_events_block_update()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS support_case_events_no_update ON support_case_events")
    op.execute("DROP FUNCTION IF EXISTS support_case_events_block_update()")
    op.drop_table("support_case_events")
    op.drop_table("support_cases")
    op.drop_column("profiles", "support_flag_note")
    op.drop_column("profiles", "support_flagged_at")
