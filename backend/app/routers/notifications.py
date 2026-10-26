import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.rate_limit import rate_limit_by_user
from app.core.security import get_current_user
from app.core.utils import parse_uuid_or_404
from app.models import Notification, Profile
from app.schemas.notification import NotificationListOut, NotificationOut, UnreadCountOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def _unread_count(db: AsyncSession, user_id: uuid.UUID) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(Notification).where(
                Notification.user_id == user_id, Notification.read_at.is_(None)
            )
        )
    ).scalar_one()


@router.get("", response_model=NotificationListOut)
async def list_notifications(
    limit: int = Query(default=20, ge=1, le=50),
    before: datetime | None = Query(default=None, description="Return notifications older than this (paging)"),
    unread_only: bool = False,
    user: Profile = Depends(rate_limit_by_user("notifications", limit=120, window_seconds=60)),
    db: AsyncSession = Depends(get_db),
):
    """The bell's list — newest first, only ever the caller's own."""
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    if before is not None:
        stmt = stmt.where(Notification.created_at < before)
    # Fetch one extra to know whether another page exists.
    rows = (await db.execute(stmt.order_by(Notification.created_at.desc(), Notification.id).limit(limit + 1))).scalars().all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "items": rows,
        "unread_count": await _unread_count(db, user.id),
        "next_before": rows[-1].created_at if has_more and rows else None,
    }


@router.get("/unread-count", response_model=UnreadCountOut)
async def unread_count(
    user: Profile = Depends(rate_limit_by_user("notifications", limit=120, window_seconds=60)),
    db: AsyncSession = Depends(get_db),
):
    """Cheap endpoint the bell polls (a partial-index count)."""
    return {"unread_count": await _unread_count(db, user.id)}


@router.post("/read-all", response_model=UnreadCountOut)
async def mark_all_read(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return {"unread_count": 0}


@router.post("/{notification_id}/read", response_model=NotificationOut)
async def mark_read(
    notification_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    nid = parse_uuid_or_404(notification_id, "Notification")
    row = (
        await db.execute(select(Notification).where(Notification.id == nid, Notification.user_id == user.id))
    ).scalar_one_or_none()
    if row is None:
        # Same answer for "doesn't exist" and "someone else's": don't leak which ids exist.
        raise HTTPException(status_code=404, detail="Notification not found")
    if row.read_at is None:
        row.read_at = datetime.now(timezone.utc)
        await db.commit()
    return row
