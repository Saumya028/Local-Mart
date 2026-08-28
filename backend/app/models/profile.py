import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func
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

    # "customer" is the safe default for anyone who just signs up.
    # Becoming a "shop_owner" happens through an explicit action later
    # (Phase 5), never just by passing a different value at signup.
    role: Mapped[str] = mapped_column(String, default="customer", server_default="customer")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
