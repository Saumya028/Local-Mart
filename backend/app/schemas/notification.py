import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    body: str
    link: str | None
    created_at: datetime
    read_at: datetime | None


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int
    # Pass back as ?before= to get the next (older) page; null when done.
    next_before: datetime | None


class UnreadCountOut(BaseModel):
    unread_count: int


class OrderEventOut(BaseModel):
    """One line of an order's history. `actor` is a safe, human label — for
    customers it never reveals a staff member's name or email."""

    id: uuid.UUID
    kind: str
    from_status: str | None
    to_status: str | None
    actor_role: str
    actor: str
    note: str | None
    meta: dict | None
    created_at: datetime
