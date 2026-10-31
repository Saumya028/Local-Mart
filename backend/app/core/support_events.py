"""
The one function every support-case change goes through:

    await case_changed(db, case, "shop_replied", actor=user, note=...)

It (1) appends a SupportCaseEvent, (2) mirrors a short, customer/shop-visible
line onto the ORDER's timeline when the case is about an order (that history is
the dispute evidence), and (3) sends in-app notifications — never email
(the product decision for support: in-app only).

Call before `db.commit()`. Recording the event is part of the business
transaction; notifying is best-effort inside a SAVEPOINT, so a notification
bug can never block a customer from reporting a problem.
"""
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.notification_templates import Msg, order_ref
from app.core.notifications import create_notification, shop_team
from app.core.order_events import order_changed
from app.core.support_rules import (
    KIND_LABELS,
    ORDER_KINDS,
    RULING_LABELS,
    reason_label,
)
from app.models import Order, Profile, Shop, SupportCase, SupportCaseEvent

logger = logging.getLogger(__name__)

# case event kind -> order-timeline kind (only for cases tied to an order).
# Notes on the order timeline are deliberately short and generic: the full
# text lives on the case.
ORDER_TIMELINE_KIND = {
    "opened": "support_opened",
    "shop_replied": "support_shop_replied",
    "escalated": "support_escalated",
    "ruled": "support_ruled",
    "action_done": "support_action_done",
    "accepted": "support_closed",
    "auto_closed": "support_closed",
}


@dataclass(frozen=True)
class Audience:
    customer: Msg | None = None
    shop: Msg | None = None
    admin: Msg | None = None
    # Shop-side link target (shop_report cases can't be opened by the shop).
    shop_can_open: bool = True


def _action_phrase(action: str | None) -> str:
    return {"refund": "refund the customer", "resend": "resend the order"}.get(action or "", "fix this")


def support_messages(kind: str, ctx: dict) -> Audience:
    """Who hears what. Pure (no database) so the wording is easy to review."""
    ref = ctx.get("ref")
    shop = ctx.get("shop_name") or "The shop"
    buyer = ctx.get("buyer_name") or "A customer"
    reason = ctx.get("reason") or "a problem"
    case_kind = ctx.get("case_kind")
    on_order = f" on order {ref}" if ref else ""
    hours = settings.support_shop_reply_hours
    days = settings.support_auto_close_days
    note = (ctx.get("note") or "").strip()
    with_note = f" “{note}”" if note else ""

    if kind == "opened":
        if case_kind in ORDER_KINDS:
            return Audience(
                shop=Msg(
                    f"Problem reported{on_order}",
                    f"{buyer} reported: {reason}. Please reply within {hours} hours so it can be sorted out.",
                )
            )
        if case_kind == "shop_report":
            return Audience(
                shop=Msg(
                    "A report was filed about your shop",
                    "A customer reported an issue with your shop. LocalMart support will look into it — "
                    "there’s nothing you need to do right now.",
                ),
                admin=Msg("New shop report", f"{shop}: {reason}."),
                shop_can_open=False,
            )
        return Audience(admin=Msg("New support request", f"{buyer}: {reason}."))

    if kind == "shop_replied":
        rtype = ctx.get("response_type")
        tail = f" If you don’t respond, this closes automatically in {days} days."
        if rtype == "accept_fix":
            body = f"{shop} agreed to fix it. Open the report to accept, or escalate to LocalMart support.{tail}"
        elif rtype == "offer":
            body = f"{shop} made you an offer. Open the report to accept it, or escalate to LocalMart support.{tail}"
        else:
            body = f"{shop} disagrees with your report. You can accept this or escalate to LocalMart support.{tail}"
        return Audience(customer=Msg(f"{shop} replied to your report", body))

    if kind == "info_requested":
        return Audience(
            customer=Msg(
                f"{shop} needs more information",
                f"Add the details they asked for so they can reply.{with_note} "
                f"If you don’t respond, this closes automatically in {days} days.",
            )
        )

    if kind == "info_provided":
        return Audience(shop=Msg(f"{buyer} added more information", f"Open the report{on_order} to reply."))

    if kind == "escalated":
        return Audience(
            shop=Msg(
                f"Report escalated to LocalMart support{on_order}",
                "The customer escalated this report. An admin will review it and may contact you.",
            ),
            admin=Msg("Report escalated", f"{buyer} escalated a {KIND_LABELS.get(case_kind, 'report').lower()} ({reason})."),
        )

    if kind == "overdue_flagged":
        return Audience(
            shop=Msg(
                f"Reply needed{on_order}",
                f"A problem reported{on_order} has had no reply for {hours} hours and was flagged to LocalMart support.",
            ),
            admin=Msg("Shop hasn’t replied (overdue)", f"{shop} hasn’t replied to a report{on_order} within {hours} hours."),
        )

    if kind == "ruled":
        line = RULING_LABELS.get(ctx.get("ruling") or "", "A decision was made")
        extra = ""
        if ctx.get("action"):
            when = f" by {ctx['deadline_text']}" if ctx.get("deadline_text") else ""
            extra = f" The shop has been asked to {_action_phrase(ctx['action'])}{when}."
        body = f"{line}.{with_note}{extra}"
        title = f"LocalMart support ruled{on_order}"
        return Audience(customer=Msg(title, body), shop=Msg(title, body))

    if kind == "action_done":
        return Audience(
            customer=Msg(
                f"{shop} says it’s done",
                f"The shop confirmed it has {'refunded you' if ctx.get('action') == 'refund' else 'resent your order'}"
                f"{on_order}. If that isn’t right, contact LocalMart support from Help.",
            )
        )

    if kind == "action_overdue":
        return Audience(
            admin=Msg(
                "Shop missed an admin deadline",
                f"{shop} hasn’t confirmed the {ctx.get('action') or 'ordered action'}{on_order}. Review and decide next steps.",
            )
        )

    if kind == "accepted":
        return Audience(shop=Msg(f"{buyer} closed the report{on_order}", "The customer accepted the outcome — nothing more to do."))

    if kind == "auto_closed":
        msg = Msg(
            f"Report closed{on_order}",
            f"There was no response for {days} days, so it was closed automatically.",
        )
        return Audience(customer=msg, shop=msg if case_kind in ORDER_KINDS else None)

    if kind == "reviewed":
        outcome = "action was taken" if ctx.get("outcome") == "action_taken" else "no action was needed"
        return Audience(customer=Msg("Your report was reviewed", f"LocalMart support reviewed it: {outcome}. Thanks for letting us know."))

    if kind == "shop_warned":
        return Audience(shop=Msg("A warning from LocalMart support", note or "Please review LocalMart’s seller rules."))

    if kind == "shop_hidden":
        return Audience(
            shop=Msg(
                "Your shop has been hidden",
                f"LocalMart support hid your shop from customers.{with_note} Contact support to get it back.",
            )
        )

    if kind == "flag_suggested":
        return Audience(
            admin=Msg(
                "Customer may be filing false disputes",
                f"{buyer} has had {ctx.get('count')} disputes ruled against them in the last 60 days. "
                "You can flag them from the case.",
            )
        )

    return Audience()


async def admins(db: AsyncSession) -> list[Profile]:
    rows = await db.execute(select(Profile).where(Profile.role == "admin", Profile.is_suspended.is_(False)))
    return list(rows.scalars().all())


async def case_changed(
    db: AsyncSession,
    case: SupportCase,
    kind: str,
    *,
    actor: Profile | None = None,
    actor_role: str | None = None,
    note: str | None = None,
    meta: dict | None = None,
    extra: dict | None = None,
) -> SupportCaseEvent:
    """`extra`: additional template context — NOT stored (`meta` is)."""
    event = SupportCaseEvent(
        case_id=case.id,
        kind=kind,
        actor_id=actor.id if actor else None,
        actor_role=actor_role or (actor.role if actor else "system"),
        note=note,
        meta=meta,
    )
    db.add(event)
    await db.flush()

    # Order timeline (evidence both sides can see). A failure here is a bug
    # worth failing on? No — the case event above is the record; the timeline
    # line is a convenience, so keep it in a savepoint too.
    timeline_kind = ORDER_TIMELINE_KIND.get(kind)
    if timeline_kind and case.order_id:
        try:
            async with db.begin_nested():
                order = await db.get(Order, case.order_id)
                if order is not None:
                    short = reason_label(case.kind, case.reason) if kind == "opened" else None
                    await order_changed(
                        db,
                        order,
                        timeline_kind,
                        actor=actor,
                        actor_role=actor_role,
                        note=short or (note[:200] if note else None),
                        meta={"case_id": str(case.id), "case_kind": case.kind, **(meta or {})},
                    )
        except Exception:
            logger.exception("support timeline line failed for case %s event %s", case.id, kind)

    try:
        async with db.begin_nested():
            await _notify(db, case, kind, event, actor, extra or {})
    except Exception:
        logger.exception("support notifications failed for case %s event %s — change itself is unaffected", case.id, kind)
    return event


async def _notify(db: AsyncSession, case: SupportCase, kind: str, event: SupportCaseEvent, actor: Profile | None, extra: dict) -> None:
    shop = await db.get(Shop, case.shop_id) if case.shop_id else None
    customer = await db.get(Profile, case.user_id)
    order = await db.get(Order, case.order_id) if case.order_id else None

    ctx = {
        "ref": order_ref(order.id) if order else None,
        "shop_name": shop.name if shop else None,
        "buyer_name": (customer.full_name if customer else None),
        "reason": reason_label(case.kind, case.reason),
        "case_kind": case.kind,
        "ruling": case.ruling,
        "note": event.note,
        "response_type": case.shop_response_type,
        "action": case.order_action,
        "outcome": case.review_outcome,
        **extra,
    }
    audience = support_messages(kind, ctx)
    actor_id = actor.id if actor else None
    data = {"case_id": str(case.id)}

    async def send(user: Profile, msg: Msg, link: str) -> None:
        if user.id == actor_id:
            return
        await create_notification(
            db, user, msg, kind=f"support_{kind}", link=link, data=data,
            dedupe_key=f"support:{event.id}:{user.id}", email=False,
        )

    if audience.customer and customer is not None:
        await send(customer, audience.customer, f"/profile?tab=support&case={case.id}")
    if audience.shop and shop is not None:
        link = f"/shop/dashboard?tab=support&case={case.id}" if audience.shop_can_open else "/shop/dashboard?tab=support"
        for member in await shop_team(db, shop):
            await send(member, audience.shop, link)
    if audience.admin:
        for admin in await admins(db):
            await send(admin, audience.admin, f"/admin?tab=support&case={case.id}")
