"""
The one function every order/payment/return change goes through:

    await order_changed(db, order, "status_changed", actor=user, from_status=..., to_status=...)

It (1) appends an OrderEvent to the order's history and (2) notifies whoever
needs to know. Call it BEFORE `db.commit()` so the history and notifications
commit atomically with the change itself.

Failure policy:
  * Recording the event is part of the business transaction — if it can't be
    written, the change fails too. History is the dispute evidence; we never
    want a change that has no record.
  * Notifying is best-effort — it runs in a SAVEPOINT, so any bug or bad data
    there rolls back only the notifications and is logged. A broken email
    template must never stop a customer from placing an order.
"""
import logging

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_templates import customer_message, money, order_ref, shop_message
from app.core.shop_hours import describe_eta, zone_of
from app.core.notifications import create_notification, shop_team
from app.core.payment_confirmation import get_payment
from app.models import Order, OrderEvent, OrderItem, Profile, Shop
from sqlalchemy import func, select

logger = logging.getLogger(__name__)


async def order_changed(
    db: AsyncSession,
    order: Order,
    kind: str,
    *,
    actor: Profile | None = None,
    actor_role: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    note: str | None = None,
    meta: dict | None = None,
    extra: dict | None = None,
) -> OrderEvent:
    """
    `actor_role`: pass "customer" explicitly from customer-facing endpoints
    (a shop owner shopping as a customer has role "shop_owner", which would
    mislabel the history). Defaults to the actor's own role, or "system"
    when there is no actor (e.g. the expiry job).

    `extra`: additional template context (return details etc.) — it is NOT
    stored; `meta` is what gets stored on the event.
    """
    event = OrderEvent(
        order_id=order.id,
        kind=kind,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor.id if actor else None,
        actor_role=actor_role or (actor.role if actor else "system"),
        note=note,
        meta=meta,
    )
    db.add(event)
    await db.flush()

    try:
        async with db.begin_nested():
            await _notify(db, order, event, actor, extra or {})
    except Exception:
        logger.exception("notifications failed for order %s event %s — change itself is unaffected", order.id, kind)
    return event


async def _notify(db: AsyncSession, order: Order, event: OrderEvent, actor: Profile | None, extra: dict) -> None:
    shop = await db.get(Shop, order.shop_id)
    buyer = await db.get(Profile, order.user_id)
    if shop is None or buyer is None:
        return
    payment = await get_payment(db, order.id)
    item_count = (
        await db.execute(select(func.coalesce(func.sum(OrderItem.quantity), 0)).where(OrderItem.order_id == order.id))
    ).scalar_one()

    now = datetime.now(timezone.utc)
    # After an ETA change the original slot no longer describes the expectation.
    keep_slot = event.kind != "eta_changed"
    fee = Decimal(str(order.delivery_fee or 0))
    ctx = {
        **(event.meta or {}),
        "eta_text": describe_eta(
            order.eta_at,
            order.slot_start if keep_slot else None,
            order.slot_end if keep_slot else None,
            zone_of(shop),
            now,
        ),
        "fee_text": f" incl. {money(fee)} delivery" if fee > 0 else "",
        "ref": order_ref(order.id),
        "shop_name": shop.name,
        "buyer_name": buyer.full_name,
        "total": money(order.total_amount),
        "fulfillment": order.fulfillment_type,
        "payment_method": payment.method if payment else None,
        "item_count": int(item_count or 0),
        "to_status": event.to_status,
        "note": event.note,
        "actor_role": event.actor_role,
        **extra,
    }

    customer_msg = customer_message(event.kind, ctx)
    shop_msg = shop_message(event.kind, ctx)
    actor_id = actor.id if actor else None

    if customer_msg:
        await create_notification(
            db, buyer, customer_msg, kind=event.kind, link=f"/orders/{order.id}",
            data={"order_id": str(order.id)}, dedupe_key=f"event:{event.id}:{buyer.id}",
        )
    if shop_msg:
        for member in await shop_team(db, shop):
            if member.id == actor_id:
                continue
            await create_notification(
                db, member, shop_msg, kind=event.kind, link="/shop/dashboard?tab=orders",
                data={"order_id": str(order.id), "shop_id": str(shop.id)},
                dedupe_key=f"event:{event.id}:{member.id}",
            )
