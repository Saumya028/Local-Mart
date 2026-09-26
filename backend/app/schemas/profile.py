import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProfileOut(BaseModel):
    """
    What we send back to the frontend for a profile. Separate from the
    SQLAlchemy model on purpose — the API's shape shouldn't be forced to
    match the database's shape 1:1 forever (e.g. we'd never want to
    accidentally expose an internal-only column just because it exists
    on the model).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    full_name: str | None
    phone: str | None
    role: str
    created_at: datetime


class ProfileUpdate(BaseModel):
    """
    My Account > Settings. Deliberately does NOT include `email` or
    `role` — email changes go through Supabase Auth (which owns login
    identity, not this table), and role changes are an admin action
    (see routers/admin.py's update_user_role), never something a user
    sets on themselves.
    """

    full_name: str | None = None
    phone: str | None = None
