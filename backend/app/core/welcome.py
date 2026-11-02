"""The one-time welcome message for a brand-new account (bell + email)."""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email_policy import should_email
from app.core.notification_templates import Msg
from app.core.notifications import create_notification
from app.models import Profile

logger = logging.getLogger(__name__)


def welcome_message(full_name: str | None) -> Msg:
    first = (full_name or "").strip().split(" ")[0]
    greeting = f"Hi {first}," if first else "Hi,"
    return Msg(
        "Welcome to LocalMart",
        f"{greeting} thanks for joining LocalMart. Browse shops near you, order what you need, "
        "and follow your order right here — we’ll let you know about the things that matter.",
    )


async def send_welcome(db: AsyncSession, profile: Profile) -> None:
    """Called once, when the profile row is first created. Exactly-once is
    guaranteed by the dedupe key even if two first requests race. Best-effort in
    a SAVEPOINT: a problem here must never block someone from logging in.
    Honors the person's email setting like every other email."""
    try:
        async with db.begin_nested():
            await create_notification(
                db, profile, welcome_message(profile.full_name),
                kind="welcome", link="/stores",
                dedupe_key=f"welcome:{profile.id}",
                email=should_email("customer", "welcome"),
            )
    except Exception:
        logger.exception("welcome message failed for %s — signup itself is unaffected", profile.id)
