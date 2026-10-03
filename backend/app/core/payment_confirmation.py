"""
Shared logic for direct (customer -> shop) payments.

The platform never sees the money, so these helpers only record what the
two parties report:

- the customer says "I've paid" (+ optional UTR)   -> mark_submitted
- the shop confirms it received the money / cash    -> mark_paid
- the shop says it did NOT receive it               -> reject_submission
- an order is cancelled -> stock reserved at checkout goes back -> cancel_order_and_release_stock

All are idempotent: repeating one changes nothing.
"""
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, OrderItem, Payment, PlatformSettings, Product


async def get_payment(db: AsyncSession, order_id) -> Payment | None:
    result = await db.execute(select(Payment).where(Payment.order_id == order_id))
    return result.scalars().first()


def mark_submitted(payment: Payment, payer_reference: str | None) -> None:
    if payment.status == "paid":
        return
    payment.status = "submitted"
    payment.payer_reference = payer_reference or None
    payment.marked_paid_at = datetime.now(timezone.utc)


def mark_paid(payment: Payment) -> None:
    if payment.status == "paid":
        return
    payment.status = "paid"
    payment.paid_at = datetime.now(timezone.utc)


def reject_submission(payment: Payment) -> None:
    """Shop says the money never arrived — back to unpaid so the customer
    can retry or switch to cash."""
    if payment.status == "paid":
        return
    payment.status = "unpaid"
    payment.marked_paid_at = None
    payment.payer_reference = None


async def cancel_order_and_release_stock(db: AsyncSession, order: Order) -> None:
    if order.status == "cancelled":
        return
    order.status = "cancelled"
    items = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    for item in items.scalars().all():
        await db.execute(
            update(Product)
            .where(Product.id == item.product_id)
            .values(stock_qty=Product.stock_qty + item.quantity)
        )


async def platform_enabled_methods(db: AsyncSession) -> set[str]:
    """Which payment methods the platform admin currently allows
    (Admin > Settings > Payment Gateway switches: "upi_direct" -> "upi",
    "cod" -> "cash"). No settings row yet means everything is allowed."""
    row = await db.get(PlatformSettings, 1)
    if row is None or not row.payment_gateways:
        return {"upi", "cash"}
    key_to_method = {"upi_direct": "upi", "cod": "cash"}
    return {
        key_to_method[g["key"]]
        for g in row.payment_gateways
        if g.get("enabled") and g.get("key") in key_to_method
    }
