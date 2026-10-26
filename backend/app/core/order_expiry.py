"""
Expires orders that would otherwise hold reserved stock forever.

Checkout reserves stock immediately (see routers/orders.py). Payments are
direct customer -> shop, so nothing forces an order to ever be paid or acted
on. This releases the stock of two kinds of stale order:

  1. UPI order, payment still "unpaid" after ORDER_UNPAID_UPI_EXPIRY_MINUTES
     (the customer never even reported paying).
  2. Any order still "confirmed" (shop never started) after
     ORDER_UNACTED_EXPIRY_HOURS, with payment still "unpaid".

Deliberately NOT expired: a payment in "submitted" (the customer says money
was sent — a human must resolve that) or "paid", and anything the shop has
started preparing. A cash order the shop is working on is also left alone.

Run it every ~15 minutes: `python -m scripts.expire_unpaid_orders`.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate
from app.core.config import settings
from app.core.order_events import order_changed
from app.core.payment_confirmation import cancel_order_and_release_stock
from app.models import Order, OrderItem, Payment

logger = logging.getLogger(__name__)

BATCH_SIZE = 200


def _duration(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{minutes} minutes"


async def expire_stale_orders(db: AsyncSession, now: datetime | None = None) -> list[str]:
    """Cancel stale unpaid orders and give their stock back. Returns the
    cancelled order ids. Commits."""
    now = now or datetime.now(timezone.utc)
    upi_cutoff = now - timedelta(minutes=settings.order_unpaid_upi_expiry_minutes)
    unacted_cutoff = now - timedelta(hours=settings.order_unacted_expiry_hours)

    # FOR UPDATE SKIP LOCKED: if a shop/customer is touching an order right
    # now (or a second sweeper is running), skip it this round rather than
    # block or double-process it.
    stmt = (
        select(Order, Payment.method)
        .join(Payment, Payment.order_id == Order.id)
        .where(
            Order.status == "confirmed",
            Payment.status == "unpaid",
            (
                ((Payment.method == "upi") & (Order.created_at < upi_cutoff))
                | (Order.created_at < unacted_cutoff)
            ),
        )
        .order_by(Order.created_at)
        .limit(BATCH_SIZE)
        .with_for_update(skip_locked=True)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    order_ids = [order.id for order, _ in rows]
    for order, method in rows:
        if method == "upi" and order.created_at < upi_cutoff:
            minutes = settings.order_unpaid_upi_expiry_minutes
            reason = f"It wasn’t paid within {_duration(minutes)}."
        else:
            reason = f"The shop didn’t start on it within {_duration(settings.order_unacted_expiry_hours * 60)}."
        await cancel_order_and_release_stock(db, order)
        await order_changed(
            db, order, "order_cancelled", actor=None,
            from_status="confirmed", to_status="cancelled", note=f"Cancelled automatically. {reason}",
        )
    product_ids = (
        await db.execute(select(OrderItem.product_id).where(OrderItem.order_id.in_(order_ids)).distinct())
    ).scalars().all()
    await db.commit()

    # Stock just changed; product pages are cached for 60s.
    await invalidate(*[f"product:{pid}" for pid in product_ids])
    logger.info("expired %d stale unpaid orders", len(order_ids))
    return [str(i) for i in order_ids]
