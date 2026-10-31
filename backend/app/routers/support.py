"""
Customer support — the customer's and the shop's halves.
(The admin's half is routers/admin_support.py.)

  Customer:  report a problem (order / payment / shop / general), add the one
             piece of information a shop may ask for, accept the outcome, or
             escalate to admin.
  Shop:      owner and manager see order + payment problems on their shop and
             send ONE structured reply (agree to fix / offer / disagree), or ask
             the customer for more information once.

Returns (routers/returns.py) are a separate feature and are untouched.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.security import get_current_user, require_role
from app.core.support_events import case_changed
from app.core.support_rules import (
    ACTION_PENDING,
    ADMIN_DIRECT_KINDS,
    CUSTOMER_ACTIVE,
    ESCALATED,
    KIND_LABELS,
    NEEDS_INFO,
    OPEN,
    ORDER_KINDS,
    REASONS,
    RESOLVED,
    SHOP_RESPONSE_TYPES,
    auto_close_window,
    order_report_block,
    shop_reply_window,
)
from app.core.support_view import serialize_cases
from app.core.utils import parse_uuid_or_404
from app.models import Order, OrderEvent, Profile, Shop, SupportCase
from app.schemas.support import (
    ActionDone,
    CaseCreate,
    EscalateRequest,
    InfoReply,
    ShopReply,
    SupportCaseOut,
    SupportOptions,
)

router = APIRouter(tags=["support"])

# Guard against a single account flooding admin with reports.
MAX_OPEN_DIRECT_CASES_PER_USER = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _my_case(db: AsyncSession, case_id: str, user: Profile, *, lock: bool = False) -> SupportCase:
    cid = parse_uuid_or_404(case_id, "Report")
    stmt = select(SupportCase).where(SupportCase.id == cid)
    if lock:
        stmt = stmt.with_for_update()
    case = (await db.execute(stmt)).scalar_one_or_none()
    if case is None or case.user_id != user.id:
        raise HTTPException(status_code=404, detail="Report not found")
    return case


async def _one(db: AsyncSession, case: SupportCase, audience: str) -> dict:
    await db.refresh(case)
    return (await serialize_cases(db, [case], audience))[0]


# ------------------------------------------------------------------ options

@router.get("/support/options", response_model=SupportOptions)
async def support_options():
    """Reason lists and the timing rules, so the frontend never hard-codes them."""
    return SupportOptions(
        kinds=[{"code": k, "label": v} for k, v in KIND_LABELS.items()],
        reasons={k: [{"code": c, "label": l} for c, l in r.items()] for k, r in REASONS.items()},
        report_window_days=settings.support_report_window_days,
        shop_reply_hours=settings.support_shop_reply_hours,
        auto_close_days=settings.support_auto_close_days,
        max_photos=settings.support_max_photos,
    )


# ----------------------------------------------------------------- customer

@router.post("/support/cases", response_model=SupportCaseOut, status_code=201)
async def create_case(
    payload: CaseCreate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    File a report.

    * order_problem / payment_problem: about one of YOUR orders; the shop gets
      the first chance to reply. One unresolved report per order. Reportable
      while the order is open, and for N days after delivery/pickup (or after
      cancellation) — see core/support_rules.order_report_block.
    * shop_report: about a shop; goes straight to admin. The shop is told a
      report exists, without details.
    * general: an app/account issue; straight to admin.
    """
    now = _now()
    case = SupportCase(
        id=uuid.uuid4(),
        kind=payload.kind,
        user_id=user.id,
        reason=payload.reason,
        description=payload.description,
        photos=payload.photos,
    )

    if payload.kind in ORDER_KINDS:
        order = (await db.execute(select(Order).where(Order.id == payload.order_id).with_for_update())).scalar_one_or_none()
        if order is None or order.user_id != user.id:
            raise HTTPException(status_code=404, detail="Order not found")

        already = await db.scalar(
            select(func.count()).select_from(SupportCase).where(SupportCase.order_id == order.id, SupportCase.status != RESOLVED)
        )
        if already:
            raise HTTPException(status_code=409, detail="You already have an open report on this order.")

        last_event_at = await db.scalar(select(func.max(OrderEvent.created_at)).where(OrderEvent.order_id == order.id))
        block = order_report_block(order.status, order.delivered_at, last_event_at, now)
        if block:
            raise HTTPException(status_code=400, detail=block)

        case.order_id = order.id
        case.shop_id = order.shop_id
        case.status = OPEN
        case.shop_due_at = now + shop_reply_window()
    else:
        open_direct = await db.scalar(
            select(func.count()).select_from(SupportCase).where(
                SupportCase.user_id == user.id, SupportCase.kind.in_(ADMIN_DIRECT_KINDS), SupportCase.status != RESOLVED
            )
        )
        if open_direct and open_direct >= MAX_OPEN_DIRECT_CASES_PER_USER:
            raise HTTPException(status_code=429, detail="You have several reports still being reviewed. Please wait for those first.")

        if payload.kind == "shop_report":
            shop = await db.get(Shop, payload.shop_id)
            if shop is None:
                raise HTTPException(status_code=404, detail="Shop not found")
            if shop.owner_id == user.id:
                raise HTTPException(status_code=400, detail="You can't report your own shop.")
            dup = await db.scalar(
                select(func.count()).select_from(SupportCase).where(
                    SupportCase.user_id == user.id, SupportCase.shop_id == shop.id,
                    SupportCase.kind == "shop_report", SupportCase.status != RESOLVED,
                )
            )
            if dup:
                raise HTTPException(status_code=409, detail="You already have an open report about this shop.")
            case.shop_id = shop.id
        # Both go straight to admin.
        case.status = ESCALATED
        case.escalated_at = now

    db.add(case)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="You already have an open report on this order.")

    await case_changed(db, case, "opened", actor=user, actor_role="customer")
    await db.commit()
    return await _one(db, case, "customer")


@router.get("/support/cases", response_model=list[SupportCaseOut])
async def list_my_cases(
    order_id: str | None = Query(default=None),
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SupportCase).where(SupportCase.user_id == user.id).order_by(SupportCase.created_at.desc()).limit(200)
    if order_id:
        stmt = stmt.where(SupportCase.order_id == parse_uuid_or_404(order_id, "Order"))
    cases = list((await db.execute(stmt)).scalars().all())
    return await serialize_cases(db, cases, "customer")


@router.get("/support/cases/{case_id}", response_model=SupportCaseOut)
async def get_my_case(case_id: str, user: Profile = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    case = await _my_case(db, case_id, user)
    return (await serialize_cases(db, [case], "customer"))[0]


@router.post("/support/cases/{case_id}/info", response_model=SupportCaseOut)
async def provide_info(
    case_id: str, payload: InfoReply, user: Profile = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Answer the shop's one request for more information. The case goes back
    to the shop with a fresh reply clock."""
    case = await _my_case(db, case_id, user, lock=True)
    if case.status != NEEDS_INFO:
        raise HTTPException(status_code=400, detail="The shop isn't waiting for more information on this report.")
    now = _now()
    case.info_reply_text = payload.message
    case.info_reply_photos = payload.photos
    case.info_replied_at = now
    case.status = OPEN
    case.shop_due_at = now + shop_reply_window()
    case.overdue_flagged_at = None
    case.auto_close_at = None
    await case_changed(db, case, "info_provided", actor=user, actor_role="customer", note=payload.message[:300])
    await db.commit()
    return await _one(db, case, "customer")


@router.post("/support/cases/{case_id}/accept", response_model=SupportCaseOut)
async def accept_outcome(case_id: str, user: Profile = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Customer is satisfied (or no longer wants to pursue it): close the report."""
    case = await _my_case(db, case_id, user, lock=True)
    if case.kind not in ORDER_KINDS or case.status not in CUSTOMER_ACTIVE:
        raise HTTPException(status_code=400, detail="This report can't be closed right now.")
    case.resolution = "accepted" if case.shop_response_type else "customer_closed"
    case.status = RESOLVED
    case.resolved_at = _now()
    case.auto_close_at = None
    await case_changed(db, case, "accepted", actor=user, actor_role="customer")
    await db.commit()
    return await _one(db, case, "customer")


@router.post("/support/cases/{case_id}/escalate", response_model=SupportCaseOut)
async def escalate_case(
    case_id: str,
    payload: EscalateRequest,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hand the report to LocalMart support. Allowed at any time while it's
    still open — the customer doesn't have to wait out the shop's reply time."""
    case = await _my_case(db, case_id, user, lock=True)
    if case.kind not in ORDER_KINDS or case.status not in CUSTOMER_ACTIVE:
        raise HTTPException(status_code=400, detail="This report can't be escalated right now.")
    case.status = ESCALATED
    case.escalated_at = _now()
    case.escalation_note = payload.note
    case.auto_close_at = None
    await case_changed(db, case, "escalated", actor=user, actor_role="customer", note=payload.note)
    await db.commit()
    return await _one(db, case, "customer")


# --------------------------------------------------------------------- shop

async def _shop_access(db: AsyncSession, shop_id: uuid.UUID | None, user: Profile) -> Shop:
    """Owner of the shop, or a manager assigned to it. (Delivery staff and other
    shops' owners get 403 — decision: only owner + manager handle disputes.)"""
    shop = await db.get(Shop, shop_id) if shop_id else None
    allowed = shop is not None and (
        shop.owner_id == user.id or (user.role == "manager" and user.shop_id == shop.id)
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="You don't have access to this shop's reports")
    return shop


RequireShopTeam = require_role("shop_owner", "manager")


@router.get("/dashboard/shops/{shop_id}/support", response_model=list[SupportCaseOut])
async def shop_cases(
    shop_id: str,
    scope: str = Query(default="all", pattern="^(all|active|closed)$"),
    user: Profile = Depends(RequireShopTeam),
    db: AsyncSession = Depends(get_db),
):
    """Order + payment problems on this shop. Shop reports are never listed here."""
    sid = parse_uuid_or_404(shop_id, "Shop")
    await _shop_access(db, sid, user)
    stmt = select(SupportCase).where(SupportCase.shop_id == sid, SupportCase.kind.in_(ORDER_KINDS))
    if scope == "active":
        stmt = stmt.where(SupportCase.status != RESOLVED)
    elif scope == "closed":
        stmt = stmt.where(SupportCase.status == RESOLVED)
    cases = list((await db.execute(stmt.order_by(SupportCase.created_at.desc()).limit(200))).scalars().all())
    return await serialize_cases(db, cases, "shop")


async def _shop_case(db: AsyncSession, case_id: str, user: Profile) -> SupportCase:
    cid = parse_uuid_or_404(case_id, "Report")
    case = (await db.execute(select(SupportCase).where(SupportCase.id == cid).with_for_update())).scalar_one_or_none()
    if case is None or case.kind not in ORDER_KINDS:
        raise HTTPException(status_code=404, detail="Report not found")
    await _shop_access(db, case.shop_id, user)
    return case


@router.post("/dashboard/support/cases/{case_id}/reply", response_model=SupportCaseOut)
async def shop_reply(
    case_id: str,
    payload: ShopReply,
    user: Profile = Depends(RequireShopTeam),
    db: AsyncSession = Depends(get_db),
):
    """The shop's single structured reply: agree to fix, make an offer, or
    disagree — each with an explanation and optional photos. OR ask the customer
    for more information, once (the customer answers, then the shop replies for
    real)."""
    case = await _shop_case(db, case_id, user)
    if case.status != OPEN:
        raise HTTPException(status_code=400, detail="This report isn't waiting for a reply from the shop.")
    now = _now()

    if payload.response_type == "need_info":
        if case.info_request_text is not None:
            raise HTTPException(status_code=400, detail="You've already asked for more information once. Please send your reply.")
        case.info_request_text = payload.message
        case.info_requested_at = now
        case.status = NEEDS_INFO
        case.shop_due_at = None
        case.auto_close_at = now + auto_close_window()
        await case_changed(db, case, "info_requested", actor=user, note=payload.message[:300])
    else:
        assert payload.response_type in SHOP_RESPONSE_TYPES
        case.shop_response_type = payload.response_type
        case.shop_response_text = payload.message
        case.shop_response_photos = payload.photos
        case.shop_responded_at = now
        case.shop_responder_id = user.id
        case.status = "shop_replied"
        case.auto_close_at = now + auto_close_window()
        await case_changed(db, case, "shop_replied", actor=user, note=payload.message[:300], meta={"response_type": payload.response_type})
    await db.commit()
    return await _one(db, case, "shop")


@router.post("/dashboard/support/cases/{case_id}/action-done", response_model=SupportCaseOut)
async def shop_action_done(
    case_id: str,
    payload: ActionDone,
    user: Profile = Depends(RequireShopTeam),
    db: AsyncSession = Depends(get_db),
):
    """The shop confirms it carried out the refund/resend an admin ordered."""
    case = await _shop_case(db, case_id, user)
    if case.status != ACTION_PENDING:
        raise HTTPException(status_code=400, detail="There's no pending admin instruction on this report.")
    now = _now()
    case.order_action_done_at = now
    case.status = RESOLVED
    case.resolution = "admin_ruling"
    case.resolved_at = now
    await case_changed(db, case, "action_done", actor=user, note=payload.note, meta={"action": case.order_action})
    await db.commit()
    return await _one(db, case, "shop")
