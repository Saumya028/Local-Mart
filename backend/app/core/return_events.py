from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_templates import money
from app.core.order_events import order_changed
from app.models import Order, OrderItem, Product, Profile, ReturnRequest


async def return_changed(
    db: AsyncSession,
    rr: ReturnRequest,
    kind: str,
    *,
    actor: Profile | None,
    actor_role: str | None = None,
    note: str | None = None,
) -> None:
    """Return/exchange activity is recorded on the ORIGINAL ORDER's history
    (one place to read the whole story) and notifies the right side. Call
    before commit, after `rr` has its new state."""
    order = await db.get(Order, rr.order_id)
    if order is None:
        return
    product_name = (
        await db.execute(
            select(Product.name).join(OrderItem, OrderItem.product_id == Product.id).where(OrderItem.id == rr.order_item_id)
        )
    ).scalar_one_or_none()
    await order_changed(
        db,
        order,
        kind,
        actor=actor,
        actor_role=actor_role,
        note=note,
        meta={"return_id": str(rr.id), "request_type": rr.request_type},
        extra={
            "product_name": product_name or "an item",
            "request_type": rr.request_type,
            "reason": rr.reason,
            "amount": money(rr.price_difference),
            "payment_method": rr.difference_method,
            "utr": rr.difference_payer_reference,
        },
    )
