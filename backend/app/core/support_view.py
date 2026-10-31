"""
Turns support cases into what each audience is allowed to see. The decision of
who sees what lives HERE, on the server: a field a viewer must not see is
simply never filled in (the UI is never trusted to hide it).

  customer  their own cases. For a shop report / general issue only the
            outcome ("action taken" / "no action needed") — never the admin's
            reasoning or the shop's identity beyond what they typed.
  shop      order + payment problems on their shop (never shop reports),
            without admin-internal notes or customer history.
  admin     everything, with names.
"""
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_templates import money, order_ref
from app.core.order_timeline import public_actor_label
from app.core.support_rules import (
    ACTION_PENDING,
    ADMIN_CAN_RULE,
    ADMIN_DIRECT_KINDS,
    CUSTOMER_ACTIVE,
    FLAG_SUGGEST_COUNT,
    FLAG_SUGGEST_WINDOW,
    KIND_LABELS,
    NEEDS_INFO,
    OPEN,
    ORDER_KINDS,
    RESOLVED,
    RULING_LABELS,
    SHOP_RESPONSE_LABELS,
    reason_label,
)
from app.models import Order, Profile, Shop, SupportCase, SupportCaseEvent

# Events only admins see (internal moderation trail).
_ADMIN_ONLY_EVENTS = {"flag_suggested", "customer_flagged", "customer_unflagged", "internal_note", "owner_suspended"}
# Admin <-> shop matters the customer isn't told about (the shop sees them).
_HIDDEN_FROM_CUSTOMER = {"shop_warned", "shop_hidden"}
# For a shop report / general issue the reporter sees just these, without notes.
_REPORTER_EVENTS = {"opened", "reviewed"}


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


async def customer_stats(db: AsyncSession, user_ids: list, now: datetime) -> dict:
    if not user_ids:
        return {}
    totals = dict(
        (await db.execute(
            select(SupportCase.user_id, func.count()).where(SupportCase.user_id.in_(user_ids)).group_by(SupportCase.user_id)
        )).all()
    )
    against = dict(
        (await db.execute(
            select(SupportCase.user_id, func.count())
            .where(
                SupportCase.user_id.in_(user_ids),
                SupportCase.ruling == "shop",
                SupportCase.ruled_at >= now - FLAG_SUGGEST_WINDOW,
            )
            .group_by(SupportCase.user_id)
        )).all()
    )
    profiles = {
        p.id: p for p in (await db.execute(select(Profile).where(Profile.id.in_(user_ids)))).scalars().all()
    }
    out = {}
    for uid in user_ids:
        n = int(against.get(uid, 0))
        p = profiles.get(uid)
        out[uid] = {
            "cases_total": int(totals.get(uid, 0)),
            "ruled_against_60d": n,
            "suggest_flag": n >= FLAG_SUGGEST_COUNT and not (p and p.support_flagged_at),
            "flagged_at": p.support_flagged_at if p else None,
            "flag_note": p.support_flag_note if p else None,
        }
    return out


def _event_visible(audience: str, case_kind: str, kind: str) -> bool:
    if audience == "admin":
        return True
    if kind in _ADMIN_ONLY_EVENTS:
        return False
    if audience == "customer" and kind in _HIDDEN_FROM_CUSTOMER:
        return False
    if audience == "customer" and case_kind in ADMIN_DIRECT_KINDS:
        return kind in _REPORTER_EVENTS
    return True


def _actor_label(audience: str, role: str, name: str | None) -> str:
    if audience == "admin":
        return f"{name} ({role})" if name else role
    if audience == "customer":
        return public_actor_label(role)
    # shop's view
    if role == "customer":
        return "The customer"
    if role == "admin":
        return "LocalMart support"
    if role in ("shop_owner", "manager", "delivery_partner"):
        return "Your shop"
    return "Automatic"


async def serialize_cases(
    db: AsyncSession, cases: list[SupportCase], audience: str, *, now: datetime | None = None
) -> list[dict]:
    assert audience in ("customer", "shop", "admin")
    now = now or datetime.now(timezone.utc)
    if not cases:
        return []

    order_ids = [c.order_id for c in cases if c.order_id]
    shop_ids = [c.shop_id for c in cases if c.shop_id]
    user_ids = list({c.user_id for c in cases})
    orders = {o.id: o for o in (await db.execute(select(Order).where(Order.id.in_(order_ids)))).scalars().all()} if order_ids else {}
    shops = {s.id: s for s in (await db.execute(select(Shop).where(Shop.id.in_(shop_ids)))).scalars().all()} if shop_ids else {}
    customers = {p.id: p for p in (await db.execute(select(Profile).where(Profile.id.in_(user_ids)))).scalars().all()}
    stats = await customer_stats(db, user_ids, now) if audience == "admin" else {}

    ev_rows = (
        await db.execute(
            select(SupportCaseEvent, Profile.full_name, Profile.email)
            .outerjoin(Profile, Profile.id == SupportCaseEvent.actor_id)
            .where(SupportCaseEvent.case_id.in_([c.id for c in cases]))
            .order_by(SupportCaseEvent.created_at, SupportCaseEvent.id)
        )
    ).all()
    events_by_case: dict = {}
    for ev, name, email in ev_rows:
        events_by_case.setdefault(ev.case_id, []).append((ev, name or email))

    out = []
    for c in cases:
        order = orders.get(c.order_id) if c.order_id else None
        shop = shops.get(c.shop_id) if c.shop_id else None
        customer = customers.get(c.user_id)
        direct = c.kind in ADMIN_DIRECT_KINDS
        reporter_view = audience == "customer" and direct
        shop_due = _aware(c.shop_due_at)
        deadline = _aware(c.order_action_deadline)

        d = {
            "id": c.id,
            "kind": c.kind,
            "kind_label": KIND_LABELS.get(c.kind, c.kind),
            "status": c.status,
            "reason": c.reason,
            "reason_label": reason_label(c.kind, c.reason),
            "description": c.description,
            "photos": list(c.photos or []),
            "resolution": c.resolution,
            "order_id": c.order_id,
            "order_ref": order_ref(order.id) if order else None,
            "order_status": order.status if order else None,
            "order_total": money(order.total_amount) if order else None,
            "shop_id": c.shop_id,
            "shop_name": shop.name if shop else None,
            "customer_name": (customer.full_name or customer.email) if customer and audience != "customer" else None,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "resolved_at": c.resolved_at,
        }

        if reporter_view:
            # Only the headline outcome — see module docstring.
            d["review_outcome"] = c.review_outcome
            d["events"] = []
        else:
            d.update(
                info_request_text=c.info_request_text,
                info_requested_at=c.info_requested_at,
                info_reply_text=c.info_reply_text,
                info_reply_photos=list(c.info_reply_photos or []),
                info_replied_at=c.info_replied_at,
                shop_response_type=c.shop_response_type,
                shop_response_label=SHOP_RESPONSE_LABELS.get(c.shop_response_type or ""),
                shop_response_text=c.shop_response_text,
                shop_response_photos=list(c.shop_response_photos or []),
                shop_responded_at=c.shop_responded_at,
                escalated_at=c.escalated_at,
                ruling=c.ruling,
                ruling_label=RULING_LABELS.get(c.ruling or ""),
                ruling_note=c.ruling_note,
                ruled_at=c.ruled_at,
                order_action=c.order_action,
                order_action_note=c.order_action_note,
                order_action_deadline=c.order_action_deadline,
                order_action_done_at=c.order_action_done_at,
                review_outcome=c.review_outcome,
                auto_close_at=c.auto_close_at,
            )
            if audience != "shop":
                d["escalation_note"] = c.escalation_note
            d["events"] = [
                {"id": ev.id, "kind": ev.kind, "actor": _actor_label(audience, ev.actor_role, nm), "note": ev.note, "created_at": ev.created_at}
                for ev, nm in events_by_case.get(c.id, [])
                if _event_visible(audience, c.kind, ev.kind)
            ]

        if audience in ("shop", "admin"):
            d["shop_due_at"] = c.shop_due_at
            d["overdue"] = bool(c.status == OPEN and shop_due and now > shop_due)
            d["action_overdue"] = bool(
                c.status == ACTION_PENDING and deadline and now > deadline and c.order_action_done_at is None
            )
        if audience == "admin":
            d["internal_note"] = c.internal_note
            d["customer_id"] = c.user_id
            d["customer_stats"] = stats.get(c.user_id)

        # What the viewer can do right now.
        if audience == "customer" and c.kind in ORDER_KINDS:
            d["can_accept"] = c.status in CUSTOMER_ACTIVE
            d["can_escalate"] = c.status in CUSTOMER_ACTIVE
            d["can_reply_info"] = c.status == NEEDS_INFO
        if audience == "shop":
            d["can_reply"] = c.status == OPEN
            d["can_request_info"] = c.status == OPEN and c.info_request_text is None
            d["can_mark_action_done"] = c.status == ACTION_PENDING
        if audience == "admin":
            d["can_rule"] = c.kind in ORDER_KINDS and c.status in ADMIN_CAN_RULE
            d["can_review"] = direct and c.status != RESOLVED
            d["can_mark_action_done"] = c.status == ACTION_PENDING
        out.append(d)
    return out
