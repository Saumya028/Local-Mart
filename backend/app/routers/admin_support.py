"""
Admin > Support: the queue of escalated disputes, shop reports and general
issues, and the admin's tools — record a ruling, order a refund/resend with a
deadline, warn / hide a shop or suspend its owner, and flag customers who keep
filing disputes that are ruled against them.

The platform never holds customers' money, so there is no "issue refund"
button: an admin's ruling is a recorded decision plus an instruction the shop
confirms. Everything an admin does is audit-logged in the same transaction.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate
from app.core.db import get_db
from app.core.security import require_role
from app.core.support_events import case_changed
from app.core.support_rules import (
    ACTION_PENDING,
    ADMIN_CAN_RULE,
    ADMIN_DIRECT_KINDS,
    ESCALATED,
    OPEN,
    ORDER_KINDS,
    RESOLVED,
)
from app.core.support_view import customer_stats, serialize_cases
from app.core.utils import escape_like, LIKE_ESCAPE_CHAR, parse_uuid_or_404
from app.models import Profile, Shop, SupportCase
from app.routers.admin import _record_audit
from app.schemas.support import (
    ActionDone,
    AdminSummary,
    FlagRequest,
    InternalNote,
    ReviewRequest,
    RuleRequest,
    ShopActionRequest,
    SupportCaseOut,
)

router = APIRouter(prefix="/admin/support", tags=["admin-support"])
RequireAdmin = require_role("admin")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _case(db: AsyncSession, case_id: str) -> SupportCase:
    cid = parse_uuid_or_404(case_id, "Report")
    case = (await db.execute(select(SupportCase).where(SupportCase.id == cid).with_for_update())).scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return case


async def _one(db: AsyncSession, case: SupportCase) -> dict:
    await db.refresh(case)
    return (await serialize_cases(db, [case], "admin"))[0]


def _attention_filters(now: datetime):
    """What needs an admin right now."""
    return or_(
        SupportCase.status == ESCALATED,
        (SupportCase.status == OPEN) & (SupportCase.shop_due_at < now),
        (SupportCase.status == ACTION_PENDING) & (SupportCase.order_action_deadline < now),
    )


@router.get("/summary", response_model=AdminSummary)
async def summary(admin: Profile = Depends(RequireAdmin), db: AsyncSession = Depends(get_db)):
    now = _now()
    async def count(*where) -> int:
        return int(await db.scalar(select(func.count()).select_from(SupportCase).where(*where)) or 0)

    return AdminSummary(
        escalated=await count(SupportCase.status == ESCALATED, SupportCase.kind.in_(ORDER_KINDS)),
        overdue=await count(SupportCase.status == OPEN, SupportCase.shop_due_at < now),
        direct_reports=await count(SupportCase.status == ESCALATED, SupportCase.kind.in_(ADMIN_DIRECT_KINDS)),
        action_overdue=await count(SupportCase.status == ACTION_PENDING, SupportCase.order_action_deadline < now),
        open_total=await count(SupportCase.status != RESOLVED),
    )


@router.get("/cases", response_model=list[SupportCaseOut])
async def list_cases(
    view: str = Query(default="attention", pattern="^(attention|escalated|overdue|reports|general|action|active|closed|all)$"),
    kind: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    now = _now()
    stmt = select(SupportCase)
    if view == "attention":
        stmt = stmt.where(_attention_filters(now))
    elif view == "escalated":
        stmt = stmt.where(SupportCase.status == ESCALATED, SupportCase.kind.in_(ORDER_KINDS))
    elif view == "overdue":
        stmt = stmt.where(SupportCase.status == OPEN, SupportCase.shop_due_at < now)
    elif view == "reports":
        stmt = stmt.where(SupportCase.kind == "shop_report", SupportCase.status != RESOLVED)
    elif view == "general":
        stmt = stmt.where(SupportCase.kind == "general", SupportCase.status != RESOLVED)
    elif view == "action":
        stmt = stmt.where(SupportCase.status == ACTION_PENDING)
    elif view == "active":
        stmt = stmt.where(SupportCase.status != RESOLVED)
    elif view == "closed":
        stmt = stmt.where(SupportCase.status == RESOLVED)
    if kind:
        stmt = stmt.where(SupportCase.kind == kind)
    if q and q.strip():
        pat = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(
            or_(
                SupportCase.user_id.in_(
                    select(Profile.id).where(
                        or_(Profile.email.ilike(pat, escape=LIKE_ESCAPE_CHAR), Profile.full_name.ilike(pat, escape=LIKE_ESCAPE_CHAR))
                    )
                ),
                SupportCase.shop_id.in_(select(Shop.id).where(Shop.name.ilike(pat, escape=LIKE_ESCAPE_CHAR))),
                cast(SupportCase.id, String).ilike(pat, escape=LIKE_ESCAPE_CHAR),
            )
        )
    # Oldest waiting first for the work queue; newest first for history views.
    order = SupportCase.created_at.desc() if view in ("closed", "all") else SupportCase.created_at.asc()
    cases = list((await db.execute(stmt.order_by(order).limit(limit).offset(offset))).scalars().all())
    return await serialize_cases(db, cases, "admin", now=now)


@router.get("/cases/{case_id}", response_model=SupportCaseOut)
async def get_case(case_id: str, admin: Profile = Depends(RequireAdmin), db: AsyncSession = Depends(get_db)):
    cid = parse_uuid_or_404(case_id, "Report")
    case = (await db.execute(select(SupportCase).where(SupportCase.id == cid))).scalar_one_or_none()
    if case is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return (await serialize_cases(db, [case], "admin"))[0]


@router.post("/cases/{case_id}/rule", response_model=SupportCaseOut)
async def rule_on_case(
    case_id: str, payload: RuleRequest, admin: Profile = Depends(RequireAdmin), db: AsyncSession = Depends(get_db)
):
    """
    Record a ruling on an order/payment dispute: in favour of the customer, the
    shop, or no fault. The note is shown to BOTH sides. When ruling for the
    customer an admin may also order the shop to refund or resend by a
    deadline; the case then waits ("action_pending") for the shop to confirm.
    Allowed on an escalated case, or on one flagged overdue / awaiting the
    customer — an admin can step in whenever it's needed.
    """
    case = await _case(db, case_id)
    if case.kind not in ORDER_KINDS:
        raise HTTPException(status_code=400, detail="Use Review for shop reports and general issues.")
    if case.status not in ADMIN_CAN_RULE:
        raise HTTPException(status_code=400, detail="This report has already been resolved or is waiting on the shop's ordered action.")
    now = _now()

    case.ruling = payload.ruling
    case.ruling_note = payload.note
    case.ruled_at = now
    case.ruled_by = admin.id
    case.auto_close_at = None
    if payload.internal_note:
        case.internal_note = payload.internal_note

    deadline_text = None
    if payload.order_action:
        case.order_action = payload.order_action
        case.order_action_note = payload.action_note
        case.order_action_deadline = now + timedelta(days=payload.action_days)
        case.order_action_done_at = None
        case.action_overdue_flagged_at = None
        case.status = ACTION_PENDING
        deadline_text = case.order_action_deadline.strftime("%d %b %Y")
    else:
        case.status = RESOLVED
        case.resolution = "admin_ruling"
        case.resolved_at = now

    _record_audit(
        db, admin, "support_ruling", "support_case", case.id,
        {"ruling": payload.ruling, "order_action": payload.order_action, "shop_id": str(case.shop_id) if case.shop_id else None},
    )
    await case_changed(
        db, case, "ruled", actor=admin, note=payload.note,
        meta={"ruling": payload.ruling, "action": payload.order_action},
        extra={"deadline_text": deadline_text},
    )

    # Third ruling against the same customer inside the window -> nudge admins.
    if payload.ruling == "shop":
        stats = (await customer_stats(db, [case.user_id], now))[case.user_id]
        if stats["suggest_flag"]:
            customer = await db.get(Profile, case.user_id)
            await case_changed(
                db, case, "flag_suggested", actor=None, actor_role="system",
                meta={"count": stats["ruled_against_60d"]},
                extra={"count": stats["ruled_against_60d"], "buyer_name": (customer.full_name or customer.email) if customer else None},
            )
    await db.commit()
    return await _one(db, case)


@router.post("/cases/{case_id}/review", response_model=SupportCaseOut)
async def review_case(
    case_id: str, payload: ReviewRequest, admin: Profile = Depends(RequireAdmin), db: AsyncSession = Depends(get_db)
):
    """Close a shop report / general issue. The reporter only ever sees
    "action taken" or "no action needed" — the reasoning stays internal."""
    case = await _case(db, case_id)
    if case.kind not in ADMIN_DIRECT_KINDS:
        raise HTTPException(status_code=400, detail="Use Rule for order and payment disputes.")
    if case.status == RESOLVED:
        raise HTTPException(status_code=400, detail="This report is already closed.")
    now = _now()
    case.review_outcome = payload.outcome
    case.reviewed_at = now
    case.status = RESOLVED
    case.resolution = "reviewed"
    case.resolved_at = now
    if payload.internal_note:
        case.internal_note = payload.internal_note
    _record_audit(db, admin, "support_review", "support_case", case.id, {"outcome": payload.outcome, "kind": case.kind})
    await case_changed(db, case, "reviewed", actor=admin, meta={"outcome": payload.outcome})
    await db.commit()
    return await _one(db, case)


@router.post("/cases/{case_id}/shop-action", response_model=SupportCaseOut)
async def shop_action(
    case_id: str, payload: ShopActionRequest, admin: Profile = Depends(RequireAdmin), db: AsyncSession = Depends(get_db)
):
    """
    Act on the shop a case is about, independent of any ruling:
      warn           sends the shop a warning (the note is shown to them)
      hide_shop      hides the shop from customers (same switch as Manage Shops)
      suspend_owner  locks the owner's account out; the shop itself stays
                     visible unless you also hide it
    """
    case = await _case(db, case_id)
    shop = await db.get(Shop, case.shop_id) if case.shop_id else None
    if shop is None:
        raise HTTPException(status_code=400, detail="This report isn't about a shop.")

    if payload.action == "warn":
        await case_changed(db, case, "shop_warned", actor=admin, note=payload.note)
    elif payload.action == "hide_shop":
        shop.is_active = False
        await case_changed(db, case, "shop_hidden", actor=admin, note=payload.note)
    else:
        owner = await db.get(Profile, shop.owner_id)
        if owner is None:
            raise HTTPException(status_code=404, detail="Shop owner not found")
        if owner.id == admin.id or owner.role == "admin":
            raise HTTPException(status_code=400, detail="That account can't be suspended from here.")
        owner.is_suspended = True
        await case_changed(db, case, "owner_suspended", actor=admin, note=payload.note)

    _record_audit(
        db, admin, f"support_{payload.action}", "shop", shop.id,
        {"case_id": str(case.id), "shop_name": shop.name, "note": payload.note},
    )
    await db.commit()
    if payload.action == "hide_shop":
        await invalidate("shops:list", f"shop:{shop.id}", "categories:list")
    return await _one(db, case)


@router.post("/cases/{case_id}/action-done", response_model=SupportCaseOut)
async def admin_action_done(
    case_id: str, payload: ActionDone, admin: Profile = Depends(RequireAdmin), db: AsyncSession = Depends(get_db)
):
    """Admin confirms the ordered refund/resend happened (e.g. after the
    customer or shop told them)."""
    case = await _case(db, case_id)
    if case.status != ACTION_PENDING:
        raise HTTPException(status_code=400, detail="There's no pending instruction on this report.")
    now = _now()
    case.order_action_done_at = now
    case.status = RESOLVED
    case.resolution = "admin_ruling"
    case.resolved_at = now
    _record_audit(db, admin, "support_action_confirmed", "support_case", case.id, {"action": case.order_action})
    await case_changed(db, case, "action_done", actor=admin, note=payload.note, meta={"action": case.order_action})
    await db.commit()
    return await _one(db, case)


@router.post("/cases/{case_id}/note", response_model=SupportCaseOut)
async def set_internal_note(
    case_id: str, payload: InternalNote, admin: Profile = Depends(RequireAdmin), db: AsyncSession = Depends(get_db)
):
    """Admin-only scratchpad on a case — never shown to customer or shop."""
    case = await _case(db, case_id)
    case.internal_note = payload.internal_note
    await db.commit()
    return await _one(db, case)


@router.post("/customers/{user_id}/flag")
async def flag_customer(
    user_id: str, payload: FlagRequest, admin: Profile = Depends(RequireAdmin), db: AsyncSession = Depends(get_db)
):
    """Mark (or unmark) a customer who keeps filing disputes ruled against
    them. Informational — it doesn't restrict the account by itself; use
    Manage Users to suspend someone."""
    uid = parse_uuid_or_404(user_id, "User")
    user = await db.get(Profile, uid)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.flagged:
        user.support_flagged_at = _now()
        user.support_flag_note = payload.note
    else:
        user.support_flagged_at = None
        user.support_flag_note = None
    _record_audit(
        db, admin, "support_customer_flagged" if payload.flagged else "support_customer_unflagged",
        "profile", user.id, {"note": payload.note},
    )
    await db.commit()
    return {"user_id": str(user.id), "flagged": payload.flagged}
