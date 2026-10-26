"""Order status history, in-app notifications, email outbox

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-21

* order_events        append-only history of every order/payment/return change
                      (UPDATEs are rejected by a trigger)
* notifications       in-app notifications (the bell)
* notification_outbox queued emails (transactional outbox, see models)
* profiles.email_notifications  per-user opt-out for emailed copies

Existing orders are back-filled with an "order_placed" event at their
created_at and, if they've moved on, one "status_changed" marked as
back-filled, so every order has a starting point on its timeline. The
back-filled rows carry no actor and say so in `note`.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_table(
        "order_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("from_status", sa.String(), nullable=True),
        sa.Column("to_status", sa.String(), nullable=True),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_role", sa.String(), nullable=False, server_default="system"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("meta", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
    )
    op.create_index("ix_order_events_order_created", "order_events", ["order_id", "created_at"])

    # History must not be editable. (Deleting an order cascades its events;
    # orders themselves are never deleted by the app.)
    op.execute(
        """
        CREATE FUNCTION order_events_block_update() RETURNS trigger AS $$
        BEGIN
            -- The ONLY permitted change: actor_id -> NULL, which is what
            -- `ON DELETE SET NULL` does when a user account is deleted (the
            -- actor_role on the row keeps recording who they were).
            IF NEW.actor_id IS NOT NULL
               OR (to_jsonb(NEW) - 'actor_id') IS DISTINCT FROM (to_jsonb(OLD) - 'actor_id') THEN
                RAISE EXCEPTION 'order_events is append-only';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER order_events_no_update BEFORE UPDATE ON order_events
        FOR EACH ROW EXECUTE FUNCTION order_events_block_update()
        """
    )

    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.String(), nullable=True),
        sa.Column("data", JSONB(), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=True, unique=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", sa.text("created_at DESC")])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    # The bell polls "how many unread?" constantly — keep that a tiny index scan.
    op.execute("CREATE INDEX ix_notifications_unread ON notifications (user_id) WHERE read_at IS NULL")

    op.create_table(
        "notification_outbox",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "notification_id", UUID(as_uuid=True), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("channel", sa.String(), nullable=False, server_default="email"),
        sa.Column("to_address", sa.String(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        "CREATE INDEX ix_outbox_due ON notification_outbox (next_attempt_at) "
        "WHERE status IN ('pending', 'sending')"
    )

    # Back-fill a starting point for orders that already exist.
    op.execute(
        """
        INSERT INTO order_events (id, order_id, kind, to_status, actor_role, note, created_at)
        SELECT gen_random_uuid(), o.id, 'order_placed', 'confirmed', 'customer',
               'Recorded from the order itself (history tracking began later)', o.created_at
        FROM orders o
        """
    )
    op.execute(
        """
        INSERT INTO order_events (id, order_id, kind, from_status, to_status, actor_role, note, created_at)
        SELECT gen_random_uuid(), o.id, 'status_changed', NULL, o.status, 'system',
               'Current status when history tracking began; earlier steps were not recorded',
               COALESCE(o.delivered_at, o.created_at)
        FROM orders o WHERE o.status <> 'confirmed'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_outbox_due")
    op.drop_table("notification_outbox")
    op.execute("DROP INDEX IF EXISTS ix_notifications_unread")
    op.drop_table("notifications")
    op.execute("DROP TRIGGER IF EXISTS order_events_no_update ON order_events")
    op.execute("DROP FUNCTION IF EXISTS order_events_block_update()")
    op.drop_table("order_events")
    op.drop_column("profiles", "email_notifications")
