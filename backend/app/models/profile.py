import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Profile(Base):
    """
    One row per user, mirroring Supabase's built-in `auth.users` table.

    We deliberately do NOT store passwords or handle login here — Supabase
    Auth already does that securely. This table exists for everything
    Supabase's auth table doesn't cover: role, display name, and anything
    else the app needs about a user.

    `id` is the SAME id Supabase issues at signup (the JWT's `sub` claim),
    not a separate auto-increment id. That's what lets us join this table
    to `auth.users` conceptually without ever touching Supabase's schema.
    """

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    # Nullable: a phone-only account (see the Login page's Phone tab) has
    # no email at all — Postgres's UNIQUE constraint still works fine
    # with this, since it treats every NULL as distinct from every other
    # NULL, so any number of phone-only profiles can coexist here.
    email: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Shown on the My Account page. For an email-based account this is
    # just a contact detail the user sets themselves via PATCH /auth/me.
    # For a phone-only account (see security.py's get_current_user) it's
    # populated automatically from the Supabase JWT on first login,
    # since it IS how that account signs in.
    phone: Mapped[str | None] = mapped_column(String, nullable=True)

    # "customer" is the safe default for anyone who just signs up.
    # Becoming a "shop_owner" happens through an explicit action later
    # (Phase 5), never just by passing a different value at signup.
    # index=True (Phase 7 hardening pass): admin.py's list_users filters
    # WHERE role = X, and platform_metrics counts rows per role — both
    # scan by this column specifically.
    role: Mapped[str] = mapped_column(
        String, default="customer", server_default="customer", index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Admin Panel "Suspend" action (Manage Users). Distinct from `role`:
    # suspending someone doesn't change what they ARE (customer/shop_owner),
    # only whether they can currently use the account. Enforced in
    # security.py's get_current_user so a suspended account is locked out
    # on the very next request, not just hidden from the UI.
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    # Staff accounts (role="manager"/"delivery_partner") are created BY a shop
    # owner, for exactly one shop — see routers/shop_dashboard.py's
    # /dashboard/staff endpoints and core/supabase_admin.py for how the
    # actual login gets provisioned. Null for every other role
    # (customer/shop_owner/admin); a shop_owner's own shops are still
    # found via Shop.owner_id, never through this column. ondelete
    # SET NULL rather than CASCADE: if a shop is ever deleted, its former
    # staff's profile rows should survive (just with no shop attached),
    # not vanish along with it.
    shop_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shops.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # ---- Customer details (collected at signup / My Account) ----------
    # All nullable: accounts created before these existed, and phone-only
    # logins, simply don't have them until the customer fills them in.
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    # "male" | "female" | "other" | "prefer_not_to_say" — see
    # core/customer_validation.py's GENDERS.
    gender: Mapped[str | None] = mapped_column(String, nullable=True)

    # "individual" (normal customer) or "business" (enterprise buying with
    # a GSTIN, e.g. to claim input tax credit). Every account starts as
    # "individual" unless the signup form says otherwise.
    customer_type: Mapped[str] = mapped_column(
        String, default="individual", server_default="individual", index=True
    )
    business_name: Mapped[str | None] = mapped_column(String, nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True, index=True)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # A GSTIN the customer typed in is only *well-formed* (checksum
    # validated), not proven to be theirs. This flips to True only through
    # an admin/verification step — never from user input — and any
    # business-only pricing/tax treatment should key off THIS, not `gstin`.
    gst_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
