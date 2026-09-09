import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
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
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    # Shown on the My Account page and used nowhere else yet (no SMS/call
    # features in the product) — purely a contact detail the user
    # maintains themselves via PATCH /auth/me.
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
