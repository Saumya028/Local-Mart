import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OrderEvent(Base):
    """
    Append-only history of everything that happens to an order: who did
    what, when. This is the evidence for disputes ("you never delivered" /
    "I never received the payment") — the Order row only holds the CURRENT
    state, so without this the story of how it got there is lost.

    A database trigger (migration 0024) rejects UPDATEs, so history can't be
    quietly rewritten, even by a bug.

    `actor_role` is stored on the row (not just joined from the profile) so
    the record stays accurate if the person's role changes or the account is
    later deleted (`actor_id` goes NULL on profile deletion; role stays).
    """

    __tablename__ = "order_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE")
    )
    # order_placed | status_changed | payment_submitted | payment_confirmed |
    # payment_rejected | payment_method_changed | order_cancelled |
    # return_requested | return_approved | return_rejected | return_completed |
    # return_cancelled | difference_reported | difference_confirmed
    kind: Mapped[str] = mapped_column(String)
    from_status: Mapped[str | None] = mapped_column(String, nullable=True)
    to_status: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    # customer | shop_owner | manager | delivery_partner | admin | system
    actor_role: Mapped[str] = mapped_column(String, default="system", server_default="system")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # clock_timestamp(), not now(): events written in one transaction must still
    # sort in the order they happened (now() is frozen at transaction start).
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class Notification(Base):
    """One in-app notification for one user (the bell icon). Email copies
    are queued separately in `NotificationOutbox`."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    # Frontend path to open when clicked, e.g. "/orders/<id>".
    link: Mapped[str | None] = mapped_column(String, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Unique so the same event can never notify the same person twice.
    dedupe_key: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.clock_timestamp())


class NotificationOutbox(Base):
    """
    Transactional outbox for outgoing messages. A row is written in the SAME
    database transaction as the business change (so an order can never be
    placed without its "new order" email being queued, and a rolled-back
    order never emails anyone). A worker (core/notification_worker.py) then
    delivers it, retrying with backoff.

    status: pending -> sending -> sent | failed (gave up after max attempts)
    A worker that dies mid-send leaves "sending" with an expired
    `locked_until`, which another worker reclaims (at-least-once delivery).
    """

    __tablename__ = "notification_outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String, default="email", server_default="email")
    to_address: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    body_text: Mapped[str] = mapped_column(Text)
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
