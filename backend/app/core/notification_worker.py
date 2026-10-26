"""
Delivers queued emails (see models/notification.py: NotificationOutbox).

Runs in two ways, both safe to use together:
  * inside the API process — a small loop started from main.py's lifespan
    (NOTIFICATION_WORKER_ENABLED=true, the default), so emails go out within
    seconds without any extra infrastructure;
  * `python -m scripts.send_notifications [--loop]` — a standalone worker/cron.

Multiple workers never double-send a row: due rows are CLAIMED with
`FOR UPDATE SKIP LOCKED` and marked "sending" with a lease (`locked_until`).
A worker that dies mid-send simply lets the lease expire and another worker
retries it — delivery is at-least-once.

Failures retry with exponential backoff (1m, 2m, 4m, 8m…) up to
NOTIFICATION_MAX_ATTEMPTS, then the row is marked "failed" (kept, with the
last error, for inspection).
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.core.email_sender import send_email
from app.models import NotificationOutbox

logger = logging.getLogger(__name__)

BATCH_SIZE = 20
LEASE = timedelta(minutes=5)


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(30 * (2**attempts), 3600))


async def _claim_due(limit: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(NotificationOutbox)
                .where(
                    or_(
                        and_(NotificationOutbox.status == "pending", NotificationOutbox.next_attempt_at <= now),
                        and_(NotificationOutbox.status == "sending", NotificationOutbox.locked_until < now),
                    )
                )
                .order_by(NotificationOutbox.next_attempt_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        ).scalars().all()
        claimed = []
        for row in rows:
            row.status = "sending"
            row.locked_until = now + LEASE
            claimed.append(
                {
                    "id": row.id,
                    "to": row.to_address,
                    "subject": row.subject,
                    "text": row.body_text,
                    "html": row.body_html,
                    "attempts": row.attempts,
                }
            )
        await db.commit()
    return claimed


async def _mark(row_id, **values) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(update(NotificationOutbox).where(NotificationOutbox.id == row_id).values(**values))
        await db.commit()


async def deliver_due(limit: int = BATCH_SIZE) -> int:
    """Send everything that's due. Returns how many rows were processed."""
    claimed = await _claim_due(limit)
    for item in claimed:
        attempts = item["attempts"] + 1
        try:
            await send_email(item["to"], item["subject"], item["text"], item["html"])
        except Exception as exc:  # noqa: BLE001 — any failure should retry, not kill the worker
            error = f"{type(exc).__name__}: {exc}"[:500]
            if attempts >= settings.notification_max_attempts:
                logger.error("email %s failed permanently after %d attempts: %s", item["id"], attempts, error)
                await _mark(item["id"], status="failed", attempts=attempts, last_error=error, locked_until=None)
            else:
                logger.warning("email %s failed (attempt %d), will retry: %s", item["id"], attempts, error)
                await _mark(
                    item["id"], status="pending", attempts=attempts, last_error=error, locked_until=None,
                    next_attempt_at=datetime.now(timezone.utc) + _backoff(attempts),
                )
        else:
            await _mark(
                item["id"], status="sent", attempts=attempts, last_error=None, locked_until=None,
                sent_at=datetime.now(timezone.utc),
            )
    return len(claimed)


async def worker_loop() -> None:
    """Runs until cancelled. Never raises (a DB blip just logs and retries)."""
    logger.info("notification worker started (provider=%s)", settings.email_provider)
    while True:
        try:
            processed = await deliver_due()
            delay = 0 if processed >= BATCH_SIZE else settings.notification_worker_interval_seconds
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("notification worker iteration failed")
            delay = 30
        await asyncio.sleep(delay)
