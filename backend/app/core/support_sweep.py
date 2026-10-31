"""
Time-based housekeeping for support cases. Run every ~15 minutes
(`python -m scripts.sweep_support`; also wired into the CI schedule next to
the order-expiry job).

  1. OVERDUE      an order/payment problem the shop hasn't replied to within
                  SUPPORT_SHOP_REPLY_HOURS (48h) is flagged to admin (and the
                  shop is nudged). The customer can already escalate any time.
  2. AUTO-CLOSE   a case waiting on the CUSTOMER — after a shop reply or an info
                  request — with no action for SUPPORT_AUTO_CLOSE_DAYS (3d)
                  closes as resolved ("auto_closed").
  3. ACTION LATE  an admin-ordered refund/resend past its deadline and not
                  confirmed -> admin is alerted to decide manually. No automatic
                  penalty (product decision).

Each case is processed in its own savepoint, so one bad row can't stop the rest.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.support_events import case_changed
from app.core.support_rules import ACTION_PENDING, NEEDS_INFO, OPEN, RESOLVED, SHOP_REPLIED
from app.models import SupportCase

logger = logging.getLogger(__name__)

BATCH_SIZE = 200


async def _each(db: AsyncSession, stmt, apply) -> int:
    rows = (await db.execute(stmt.with_for_update(skip_locked=True).limit(BATCH_SIZE))).scalars().all()
    done = 0
    for case in rows:
        try:
            async with db.begin_nested():
                await apply(case)
            done += 1
        except Exception:
            logger.exception("support sweep failed for case %s", case.id)
    return done


async def sweep_support(db: AsyncSession, now: datetime | None = None) -> dict[str, int]:
    """Returns how many cases each step touched. Commits."""
    now = now or datetime.now(timezone.utc)

    async def flag_overdue(case: SupportCase) -> None:
        case.overdue_flagged_at = now
        await case_changed(db, case, "overdue_flagged", actor=None, actor_role="system")

    async def auto_close(case: SupportCase) -> None:
        case.status = RESOLVED
        case.resolution = "auto_closed"
        case.resolved_at = now
        case.auto_close_at = None
        await case_changed(db, case, "auto_closed", actor=None, actor_role="system")

    async def flag_action(case: SupportCase) -> None:
        case.action_overdue_flagged_at = now
        await case_changed(db, case, "action_overdue", actor=None, actor_role="system")

    counts = {
        "overdue": await _each(
            db,
            select(SupportCase).where(
                SupportCase.status == OPEN, SupportCase.shop_due_at < now, SupportCase.overdue_flagged_at.is_(None)
            ),
            flag_overdue,
        ),
        "auto_closed": await _each(
            db,
            select(SupportCase).where(
                SupportCase.status.in_((SHOP_REPLIED, NEEDS_INFO)), SupportCase.auto_close_at < now
            ),
            auto_close,
        ),
        "action_overdue": await _each(
            db,
            select(SupportCase).where(
                SupportCase.status == ACTION_PENDING,
                SupportCase.order_action_deadline < now,
                SupportCase.order_action_done_at.is_(None),
                SupportCase.action_overdue_flagged_at.is_(None),
            ),
            flag_action,
        ),
    }
    await db.commit()
    return counts
