import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SupportCase(Base):
    """
    One thing a customer reported. Four kinds (see core/support_rules.py):

      order_problem / payment_problem  tied to ONE order; the shop gets the
                                       first chance to reply, the customer can
                                       escalate to admin at any time.
      shop_report / general            go straight to admin (no shop reply).

    status flow (order + payment problems):
        open -> shop_replied -> resolved          (customer accepts / auto-close)
        open -> needs_info -> open                (shop asks once, customer answers)
        open|needs_info|shop_replied -> escalated -> resolved | action_pending
        action_pending -> resolved                (shop did the refund/resend)
    shop_report / general:  escalated -> resolved (admin "review", no ruling)

    Returns are a separate feature (return_requests) and are untouched.
    """

    __tablename__ = "support_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String, index=True)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True
    )
    shop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="SET NULL"), nullable=True, index=True
    )

    reason: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    photos: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    status: Mapped[str] = mapped_column(String, default="open", server_default="open", index=True)
    # accepted | customer_closed | auto_closed | admin_ruling | reviewed
    resolution: Mapped[str | None] = mapped_column(String, nullable=True)

    # --- shop's side (order + payment problems only) -------------------
    shop_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overdue_flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # The shop may ask the customer for more information exactly once.
    info_request_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    info_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    info_reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    info_reply_photos: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    info_replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # The shop's single structured reply: accept_fix | offer | disagree
    shop_response_type: Mapped[str | None] = mapped_column(String, nullable=True)
    shop_response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    shop_response_photos: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    shop_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shop_responder_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    # If the customer does nothing after a shop reply / info request the case
    # closes itself at this time (core/support_sweep.py).
    auto_close_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- escalation -----------------------------------------------------
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- admin ----------------------------------------------------------
    # customer | shop | no_fault — visible to both sides.
    ruling: Mapped[str | None] = mapped_column(String, nullable=True)
    ruling_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ruled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ruled_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    # "Order the shop to refund or resend, by <deadline>". The platform never
    # holds the money, so this is an instruction the shop confirms, not a
    # transfer. A missed deadline only alerts admin (no automatic penalty).
    order_action: Mapped[str | None] = mapped_column(String, nullable=True)  # refund | resend
    order_action_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_action_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    order_action_done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    action_overdue_flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # shop_report / general: all the reporter ever sees of the outcome.
    review_outcome: Mapped[str | None] = mapped_column(String, nullable=True)  # action_taken | no_action
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Admin-only; never serialized to customers or shops.
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # One open report per order, enforced by the database (the router also
        # checks, to give a friendly message first).
        Index(
            "uq_support_cases_one_open_per_order",
            "order_id",
            unique=True,
            postgresql_where=text("order_id IS NOT NULL AND status <> 'resolved'"),
        ),
        Index("ix_support_cases_shop_status", "shop_id", "status"),
        Index("ix_support_cases_user_created", "user_id", "created_at"),
    )


class SupportCaseEvent(Base):
    """Append-only history of a case (migration 0028 blocks UPDATEs), so who
    said or decided what, and when, can't be quietly rewritten."""

    __tablename__ = "support_case_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_cases.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    # customer | shop_owner | manager | admin | system
    actor_role: Mapped[str] = mapped_column(String, default="system", server_default="system")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())
