import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Shop(Base):
    """
    A shop is owned by exactly one profile (the seller). Every product
    belongs to a shop, never directly to a user — this is what makes the
    "platform, not seller" model concrete in the data: the platform never
    owns inventory, a shop does.
    """

    __tablename__ = "shops"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )

    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    # index=True (Phase 7 hardening pass): every foreign key should have
    # one, even though nothing currently filters WHERE on it directly —
    # this is the "confirm indexes exist on every foreign key" line item,
    # not just the ones already on a hot read path.
    address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True, index=True
    )

    rating: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    # Admin can deactivate a shop (Phase 6) without deleting its data.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    # Admin Panel shop-approval workflow ("Manage Shops" > Pending
    # Approval). A brand-new shop starts "pending" and invisible on the
    # public catalog (list_shops filters on this) until an admin approves
    # it — is_active is a SEPARATE, later concern ("is this approved shop
    # currently open"), not the same flag as approval. Existing rows get
    # server_default "approved" so shops that predate this feature don't
    # vanish from the storefront.
    approval_status: Mapped[str] = mapped_column(
        String, default="pending", server_default="approved", index=True
    )
    # Whether the seller's KYC/registration documents have been checked.
    # Independent of approval_status: an admin can request docs on an
    # already-pending application without touching its approval state.
    docs_status: Mapped[str] = mapped_column(
        String, default="pending", server_default="verified"
    )
    # Uploaded verification documents: [{"name": "...", "doc_type": "...",
    # "url": "..."}]. Never exposed by the PUBLIC shop schema (ShopOut in
    # app/schemas/shop.py) — only the owning shop_owner (via /dashboard)
    # and admins (via /admin) can ever see these URLs. A brand-new
    # application can't be created without at least one document (see
    # ShopCreate's validator), so this starts non-empty in practice.
    documents: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    # Set by an admin on reject (see routers/admin.py's reject_shop) so a
    # rejected owner knows what to fix before reapplying — cleared again
    # the next time they resubmit.
    rejection_reason: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Composite index (Phase 7): GET /shops's hottest query is exactly
    # `WHERE is_active = true ORDER BY rating DESC LIMIT 50` — this one
    # index serves both the filter and the sort together, rather than
    # Postgres using a single-column index for one and sorting the rest
    # in memory.
    __table_args__ = (Index("ix_shops_is_active_rating", "is_active", "rating"),)
