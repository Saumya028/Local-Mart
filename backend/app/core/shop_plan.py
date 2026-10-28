"""
Everything that decides whether — and on what terms — a shop will take one
customer's order: is it open, is the minimum met, what's the delivery fee,
which time slot, what ETA.

ONE function, `plan_shop_order`, is used by both:
  * POST /orders/quote  — so the checkout page can show fees, warnings and
    slots live, collecting every problem;
  * POST /orders        — the real checkout, which refuses on the first
    problem and uses the same numbers.
Because it's the same code, what the customer was shown can never disagree
with what's enforced.
"""
import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.shop_hours import OpenStatus, local_time_text, open_status, open_windows, zone_of
from app.models import Order, Shop

CENT = Decimal("0.01")
MAX_SLOTS_SHOWN = 120


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def inr(value) -> str:
    v = money(value)
    return f"₹{v:,.0f}" if v == v.to_integral_value() else f"₹{v:,.2f}"


# ------------------------------------------------------------------ fees

def delivery_fee_for(shop: Shop, subtotal: Decimal, fulfillment: str) -> Decimal:
    if fulfillment != "delivery":
        return Decimal("0.00")
    fee = money(shop.delivery_fee or 0)
    free_above = shop.free_delivery_above
    if fee > 0 and free_above is not None and subtotal >= money(free_above):
        return Decimal("0.00")
    return fee


def min_order_shortfall(shop: Shop, subtotal: Decimal, fulfillment: str) -> Decimal:
    """Minimums apply to DELIVERY only: nobody needs to be talked out of
    walking in to buy one item."""
    if fulfillment != "delivery":
        return Decimal("0.00")
    return max(Decimal("0.00"), money(shop.min_order_amount or 0) - subtotal)


# ----------------------------------------------------------------- slots

def _lead(shop: Shop, fulfillment: str) -> timedelta:
    minutes = shop.prep_time_minutes + (shop.delivery_time_minutes if fulfillment == "delivery" else 0)
    return timedelta(minutes=minutes)


def generate_slot_times(shop: Shop, fulfillment: str, now: datetime) -> list[tuple[datetime, datetime]]:
    """Every bookable slot (start, end) in UTC: aligned to the slot length on
    the shop's local clock, fully inside opening hours, outside any vacation,
    no sooner than prep (+ delivery) time from now, within `slot_days_ahead`
    calendar days. Capacity is NOT considered here."""
    if not shop.slots_enabled:
        return []
    zone = zone_of(shop)
    earliest = now + _lead(shop, fulfillment)
    last_day = now.astimezone(zone).date() + timedelta(days=shop.slot_days_ahead)  # exclusive
    horizon = datetime.combine(last_day, time(0, 0), tzinfo=zone).astimezone(timezone.utc)
    length = shop.slot_length_minutes
    step = timedelta(minutes=length)

    slots: list[tuple[datetime, datetime]] = []
    for w_start, w_end in open_windows(shop, earliest, horizon, now):
        local = w_start.astimezone(zone)
        midnight = datetime.combine(local.date(), time(0, 0), tzinfo=zone)
        minutes_in = (local - midnight).total_seconds() / 60
        first = midnight + timedelta(minutes=math.ceil(minutes_in / length) * length)
        cur = first.astimezone(timezone.utc)
        while cur + step <= w_end and len(slots) < MAX_SLOTS_SHOWN:
            slots.append((cur, cur + step))
            cur += step
    return slots


async def booked_counts(db: AsyncSession, shop_id, starts: list[datetime]) -> dict[datetime, int]:
    if not starts:
        return {}
    rows = await db.execute(
        select(Order.slot_start, func.count())
        .where(Order.shop_id == shop_id, Order.slot_start.in_(starts), Order.status != "cancelled")
        .group_by(Order.slot_start)
    )
    return {start: n for start, n in rows.all()}


async def lock_slot(db: AsyncSession, shop_id, slot_start: datetime) -> None:
    """Serialise bookings of ONE slot: two customers grabbing the last place
    at the same moment can't both pass the capacity check. The lock lasts to
    the end of the checkout transaction."""
    digest = hashlib.sha256(f"{shop_id}:{int(slot_start.timestamp())}".encode()).digest()
    key = int.from_bytes(digest[:8], "big", signed=True)
    await db.execute(select(func.pg_advisory_xact_lock(key)))


async def list_slots(db: AsyncSession, shop: Shop, fulfillment: str, now: datetime) -> list[dict]:
    times = generate_slot_times(shop, fulfillment, now)
    counts = await booked_counts(db, shop.id, [s for s, _ in times])
    zone = zone_of(shop)
    out = []
    for start, end in times:
        remaining = max(0, shop.slot_capacity - counts.get(start, 0))
        out.append(
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
                "label": f"{local_time_text(start, zone, now)} – {local_time_text(end, zone, now).replace('tomorrow ', '')}",
                "remaining": remaining,
                "available": remaining > 0,
            }
        )
    return out


# ------------------------------------------------------------------ plan

@dataclass
class Issue:
    code: str
    message: str
    http_status: int = 400


@dataclass
class ShopPlan:
    shop: Shop
    fulfillment: str
    subtotal: Decimal
    delivery_fee: Decimal
    total: Decimal
    min_order_amount: Decimal
    min_order_shortfall: Decimal
    free_delivery_above: Decimal | None
    free_delivery_remaining: Decimal | None
    status: OpenStatus
    slot: tuple[datetime, datetime] | None
    eta_at: datetime | None
    issues: list[Issue] = field(default_factory=list)


def _closed_message(shop: Shop, status: OpenStatus, now: datetime, can_schedule: bool) -> str:
    zone = zone_of(shop)
    if status.state == "temporarily_closed":
        msg = f'"{shop.name}" is temporarily closed'
        if status.message:
            msg += f" ({status.message})"
        if status.opens_at:
            msg += f" — back {local_time_text(status.opens_at, zone, now)}"
        return msg + "."
    msg = f'"{shop.name}" is closed right now'
    if status.opens_at:
        msg += f" — opens {local_time_text(status.opens_at, zone, now)}"
    msg += "."
    if can_schedule:
        msg += " You can still schedule your order for a later time slot."
    return msg


async def plan_shop_order(
    db: AsyncSession,
    shop: Shop,
    subtotal: Decimal,
    fulfillment: str,
    slot_start: datetime | None,
    *,
    now: datetime | None = None,
    lock: bool = False,
) -> ShopPlan:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    subtotal = money(subtotal)
    fee = delivery_fee_for(shop, subtotal, fulfillment)
    shortfall = min_order_shortfall(shop, subtotal, fulfillment)
    free_above = money(shop.free_delivery_above) if shop.free_delivery_above is not None else None
    free_remaining = (
        max(Decimal("0.00"), free_above - subtotal)
        if fulfillment == "delivery" and free_above is not None and money(shop.delivery_fee or 0) > 0 and fee > 0
        else None
    )
    status = open_status(shop, now)
    plan = ShopPlan(
        shop=shop, fulfillment=fulfillment, subtotal=subtotal, delivery_fee=fee, total=subtotal + fee,
        min_order_amount=money(shop.min_order_amount or 0), min_order_shortfall=shortfall,
        free_delivery_above=free_above, free_delivery_remaining=free_remaining,
        status=status, slot=None, eta_at=None,
    )

    if not shop.is_active or shop.approval_status != "approved":
        plan.issues.append(Issue("shop_unavailable", f'"{shop.name}" isn’t taking orders right now.', 409))
        return plan

    if shortfall > 0:
        plan.issues.append(
            Issue(
                "below_minimum",
                f'The minimum order for delivery from "{shop.name}" is {inr(plan.min_order_amount)} — '
                f"add {inr(shortfall)} more, or choose pickup.",
                400,
            )
        )

    if slot_start is not None:
        slot_start = slot_start.astimezone(timezone.utc)
        match = next((s for s in generate_slot_times(shop, fulfillment, now) if s[0] == slot_start), None)
        if not shop.slots_enabled:
            plan.issues.append(Issue("slots_unavailable", f'"{shop.name}" doesn’t offer scheduled time slots.', 400))
        elif match is None:
            msg = (
                _closed_message(shop, status, now, False)
                if status.state == "temporarily_closed"
                else "That time slot isn’t available any more. Please pick another."
            )
            plan.issues.append(Issue("slot_invalid", msg, 409))
        else:
            if lock:
                await lock_slot(db, shop.id, match[0])
            booked = (await booked_counts(db, shop.id, [match[0]])).get(match[0], 0)
            if booked >= shop.slot_capacity:
                plan.issues.append(Issue("slot_full", "That time slot just filled up. Please pick another.", 409))
            else:
                plan.slot = match
                plan.eta_at = match[1]
    else:
        if not status.is_open:
            can_schedule = shop.slots_enabled and bool(generate_slot_times(shop, fulfillment, now))
            plan.issues.append(Issue("shop_closed", _closed_message(shop, status, now, can_schedule), 409))
        else:
            plan.eta_at = now + _lead(shop, fulfillment)
    return plan
