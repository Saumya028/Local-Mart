import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# The two roles a shop owner can grant — never "shop_owner" or "admin"
# through this path. Becoming either of those stays exactly how it
# already worked before this feature (self-service application /
# scripts/promote_user.py), untouched by anything here.
#
# Reuses "delivery_partner" rather than inventing a second term for the
# same concept — see app/schemas/admin.py's VALID_ROLES/UsersSummary,
# which already reserved this role name for the Admin Panel's "Manage
# Users" counts, before any actual account could ever hold it. A shop's
# own delivery hire IS a delivery partner; this feature is simply the
# first real way to become one, with a shop_id attached.
StaffRole = Literal["manager", "delivery_partner"]


class StaffCreate(BaseModel):
    shop_id: uuid.UUID
    full_name: str = Field(min_length=1, max_length=200)
    # Plain str, not EmailStr — matches this codebase's existing
    # convention (see schemas/admin.py) rather than pulling in the
    # separate email-validator dependency EmailStr needs. Supabase's own
    # Admin API is what actually rejects a malformed address.
    email: str = Field(min_length=3, max_length=320)
    # The owner picks this themselves and shares it manually — see
    # core/supabase_admin.py's create_supabase_user. Same minimum
    # Supabase itself enforces on self-service signup, so a staff
    # account is never held to a weaker bar than a normal one.
    password: str = Field(min_length=8, max_length=72)
    staff_role: StaffRole


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str | None
    email: str | None
    role: str
    is_suspended: bool
    created_at: datetime


class StaffUpdate(BaseModel):
    """Staff tab's edit actions. All optional — an owner might only be
    toggling `is_suspended` (Suspend/Reactivate), only changing
    `staff_role` (promote a delivery hire to manager), or only resetting
    a password, not all three at once."""

    full_name: str | None = None
    staff_role: StaffRole | None = None
    is_suspended: bool | None = None
    new_password: str | None = Field(default=None, min_length=8, max_length=72)
