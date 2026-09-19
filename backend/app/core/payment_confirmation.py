from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, OrderItem, Payment, Product

"""
Two ways an order gets confirmed reach this same logic:

1. The Razorpay webhook (routers/webhooks.py) — the source of truth,
   signed server-to-server, works regardless of what the shopper's
   browser does after paying.
2. The client-triggered verify endpoint (POST /orders/verify-payment in
   routers/orders.py) — called right after Razorpay's Checkout popup
   reports success, verified via the SAME signature check Razorpay's own
   docs recommend for this. This exists because the webhook is a
   separate piece of infrastructure that has to be registered against
   whatever URL the backend is currently reachable at (see README's
   "Local dev" note on webhooks.py, which literally has you install a
   tunnel to make it reachable at all) — miss that step, point it at a
   stale URL after a redeploy, or have the webhook call blocked/delayed,
   and a real, successful payment sits stuck at "Awaiting payment"
   forever with nothing to ever flip it. This path doesn't replace the
   webhook (which still matters for confirmations that don't route
   through this browser at all — a payment retried from Razorpay's own
   dashboard, for instance) - it just means the *common* case doesn't
   depend on that infrastructure being wired up correctly.

Both call the functions below with the same `provider_ref` (our Payment
row's pointer to the Razorpay Order, not the Payment id) so a shop
owner's dashboard and a shopper's order tracking page see identical
results no matter which path actually got there first — and calling
either one twice for the same payment is harmless (flipping an
already-"succeeded" row to "succeeded" again, or an already-released
stock line to released again, changes nothing).
"""


async def mark_payment_captured(db: AsyncSession, provider_ref: str, method: str | None = None) -> bool:
    """Returns True if at least one Payment row matched `provider_ref`."""
    result = await db.execute(select(Payment).where(Payment.provider_ref == provider_ref))
    payments = result.scalars().all()

    for payment in payments:
        payment.status = "succeeded"
        if method:
            payment.method = method
        await db.execute(update(Order).where(Order.id == payment.order_id).values(status="confirmed"))

    return len(payments) > 0


async def mark_payment_failed(db: AsyncSession, provider_ref: str) -> bool:
    """Returns True if at least one Payment row matched `provider_ref`."""
    result = await db.execute(select(Payment).where(Payment.provider_ref == provider_ref))
    payments = result.scalars().all()

    for payment in payments:
        payment.status = "failed"
        await db.execute(update(Order).where(Order.id == payment.order_id).values(status="payment_failed"))

        # Release the stock reserved at checkout time — this order is
        # never going to be fulfilled, so holding onto that stock would
        # incorrectly block other customers from buying it.
        items_result = await db.execute(select(OrderItem).where(OrderItem.order_id == payment.order_id))
        for item in items_result.scalars().all():
            await db.execute(
                update(Product)
                .where(Product.id == item.product_id)
                .values(stock_qty=Product.stock_qty + item.quantity)
            )

    return len(payments) > 0
