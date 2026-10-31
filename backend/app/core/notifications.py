"""
Creating notifications: an in-app row (the bell) and — if the user has an
email address and hasn't opted out — a queued email in the outbox.

Both rows are written in the CALLER's database transaction (nothing is
committed here), so a notification exists if and only if the change that
caused it was committed.
"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.notification_templates import Msg, render_email
from app.models import Notification, NotificationOutbox, Profile, Shop

logger = logging.getLogger(__name__)


def public_url(path: str | None) -> str | None:
    """Absolute link for emails: first FRONTEND_ORIGIN + the frontend path."""
    if not path:
        return None
    base = settings.frontend_origin.split(",")[0].strip().rstrip("/")
    return f"{base}{path}"


async def shop_team(db: AsyncSession, shop: Shop) -> list[Profile]:
    """Who should hear about a shop's orders: the owner and any managers.
    (Delivery partners only move orders along — they aren't paged for new
    orders or payments.) Suspended accounts are skipped."""
    owner_or_manager = (Profile.id == shop.owner_id) | ((Profile.role == "manager") & (Profile.shop_id == shop.id))
    result = await db.execute(select(Profile).where(owner_or_manager, Profile.is_suspended.is_(False)))
    return list(result.scalars().all())


async def create_notification(
    db: AsyncSession,
    user: Profile,
    msg: Msg,
    *,
    kind: str,
    link: str | None,
    data: dict | None = None,
    dedupe_key: str | None = None,
    email: bool = True,
) -> bool:
    """Returns False if this exact notification already existed (dedupe).

    `email=False` makes it in-app only (the bell) — used by customer support,
    which deliberately doesn't email."""
    notification_id = uuid.uuid4()
    inserted = await db.execute(
        pg_insert(Notification)
        .values(
            id=notification_id,
            user_id=user.id,
            kind=kind,
            title=msg.title,
            body=msg.body,
            link=link,
            data=data,
            dedupe_key=dedupe_key,
        )
        .on_conflict_do_nothing(index_elements=[Notification.dedupe_key])
        .returning(Notification.id)
    )
    if inserted.first() is None:
        return False

    if email and user.email and user.email_notifications:
        text, html_body = render_email(msg, public_url(link))
        db.add(
            NotificationOutbox(
                id=uuid.uuid4(),
                notification_id=notification_id,
                channel="email",
                to_address=user.email,
                subject=msg.title,
                body_text=text,
                body_html=html_body,
            )
        )
    return True
