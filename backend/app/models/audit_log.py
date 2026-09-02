import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """
    One row per admin action. The roadmap calls this out explicitly:
    "Admin actions logged (who approved what, when) — an audit trail,
    not just a feature." Written in the SAME transaction as the change it
    records (see routers/admin.py's `_record_audit`), so there's never a
    window where an action succeeded but went unlogged, or vice versa.

    We deliberately do NOT try to be clever about `target_id`'s type —
    it's just a UUID, and `target_type` (e.g. "profile", "shop") tells you
    which table to look it up in. A generic audit log that has to support
    logging actions against any current or future entity type isn't worth
    a separate FK-per-entity-type schema.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ondelete="SET NULL" (not CASCADE): if an admin account is ever
    # deleted, their past actions should still show up in the log — an
    # audit trail that disappears when the actor's account does would
    # defeat the point of having one.
    admin_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )

    action: Mapped[str] = mapped_column(String, index=True)  # e.g. "role_change", "shop_status_change"
    target_type: Mapped[str] = mapped_column(String)  # e.g. "profile", "shop"
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Free-form before/after snapshot — e.g. {"old_role": "customer", "new_role": "shop_owner", "email": "..."}
    details: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
