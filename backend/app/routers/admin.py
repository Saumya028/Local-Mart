import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate
from app.core.db import get_db
from app.core.order_status import RECOGNIZED_STATUSES as RECOGNIZED_ORDER_STATUSES
from app.core.security import require_role
from app.core.utils import parse_uuid_or_404
from app.models import Address, AuditLog, Order, PlatformSettings, Product, Profile, Shop
from app.schemas.admin import (
    AdminShopOut,
    AdminUserOut,
    AuditLogOut,
    CategoryShare,
    DashboardSummary,
    MonthPoint,
    PlatformMetrics,
    PlatformSettingsOut,
    PlatformSettingsUpdate,
    RejectShopRequest,
    RoleUpdate,
    ShopStatusUpdate,
    UsersSummary,
    UserStatusUpdate,
    VALID_APPROVAL_STATUSES,
)

router = APIRouter(prefix="/admin", tags=["admin"])

# Every route in this file requires role="admin" specifically — not
# "shop_owner, admin" the way shop_dashboard.py does. A shop owner has no
# business here at all; this is the one place in the app that isn't
# scoped to "your own stuff", so the roadmap's own warning applies most
# strongly here: "admin routes are the highest-value target for
# privilege escalation bugs — test role checks here harder than anywhere
# else."
RequireAdmin = require_role("admin")


def _record_audit(
    db: AsyncSession,
    admin: Profile,
    action: str,
    target_type: str,
    target_id: uuid.UUID | None,
    details: dict,
) -> None:
    """
    Adds an AuditLog row to the SAME session/transaction as the change
    that triggered it — called BEFORE `db.commit()`, never after. That's
    deliberate: if we logged in a separate transaction after the fact, a
    crash between the two commits would leave an admin action that
    happened but was never recorded, which defeats the entire point of
    an audit trail. One `db.commit()` call per endpoint makes the change
    and its log entry atomic — both happen or neither does.
    """
    db.add(
        AuditLog(
            id=uuid.uuid4(),
            admin_id=admin.id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
    )


def _month_bounds(months_back: int) -> tuple[datetime, datetime]:
    """Returns (start, end) UTC bounds for "N months ago" as a calendar month."""
    now = datetime.now(timezone.utc)
    first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Walk back `months_back` calendar months from the first of this month.
    year = first_of_this_month.year
    month = first_of_this_month.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    start = first_of_this_month.replace(year=year, month=month)
    end_month = start.month + 1
    end_year = start.year
    if end_month > 12:
        end_month = 1
        end_year += 1
    end = start.replace(year=end_year, month=end_month)
    return start, end


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    role: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Case-insensitive substring match on email"),
    limit: int = Query(default=200, le=500),
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    order_counts = (
        select(Order.user_id, func.count().label("orders_count"))
        .group_by(Order.user_id)
        .subquery()
    )

    stmt = select(Profile, func.coalesce(order_counts.c.orders_count, 0)).outerjoin(
        order_counts, order_counts.c.user_id == Profile.id
    )
    if role is not None:
        stmt = stmt.where(Profile.role == role)
    if q:
        stmt = stmt.where(Profile.email.ilike(f"%{q}%"))
    stmt = stmt.order_by(Profile.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    return [
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "created_at": user.created_at,
            "is_suspended": user.is_suspended,
            "orders_count": orders_count,
        }
        for user, orders_count in result.all()
    ]


@router.patch("/users/{user_id}/role", response_model=AdminUserOut)
async def update_user_role(
    user_id: str,
    payload: RoleUpdate,
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    THE approval action the roadmap describes: this is what replaces
    `scripts/promote_user.py` for day-to-day use — approving a customer
    as a seller (or, just as importantly, demoting a shop_owner or
    revoking another admin's access) now happens from the Admin Panel UI
    instead of a script someone has to SSH in and run.

    An admin can never change their OWN role through this endpoint. This
    isn't about distrust — it's a lockout guard: if the only admin
    account demoted itself (even by an intended-for-someone-else misclick
    on a shared screen), there would be no admin left to undo it from the
    UI, only `scripts/promote_user.py` run directly against the database.
    Changing your own role stays a deliberate, out-of-band action.
    """
    uid = parse_uuid_or_404(user_id, "User")

    if uid == admin.id:
        raise HTTPException(
            status_code=400,
            detail=(
                "You can't change your own role from here — "
                "use scripts/promote_user.py if you really need to."
            ),
        )

    result = await db.execute(select(Profile).where(Profile.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = user.role
    user.role = payload.role

    _record_audit(
        db,
        admin,
        action="role_change",
        target_type="profile",
        target_id=user.id,
        details={"email": user.email, "old_role": old_role, "new_role": payload.role},
    )

    await db.commit()
    await db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "created_at": user.created_at,
        "is_suspended": user.is_suspended,
        "orders_count": 0,
    }


@router.patch("/users/{user_id}/status", response_model=AdminUserOut)
async def update_user_status(
    user_id: str,
    payload: UserStatusUpdate,
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    The "Suspend" / "Reactivate" action on Manage Users. Enforced for
    real in security.py's get_current_user — a suspended account is
    locked out of every endpoint on its very next request, not just
    hidden from this UI.
    """
    uid = parse_uuid_or_404(user_id, "User")

    if uid == admin.id and payload.is_suspended:
        raise HTTPException(status_code=400, detail="You can't suspend your own account.")

    result = await db.execute(select(Profile).where(Profile.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_suspended = payload.is_suspended

    _record_audit(
        db,
        admin,
        action="user_suspended" if payload.is_suspended else "user_reactivated",
        target_type="profile",
        target_id=user.id,
        details={"email": user.email},
    )

    await db.commit()
    await db.refresh(user)

    orders_count = await db.scalar(select(func.count()).select_from(Order).where(Order.user_id == uid))
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "created_at": user.created_at,
        "is_suspended": user.is_suspended,
        "orders_count": orders_count or 0,
    }


@router.get("/users-summary", response_model=UsersSummary)
async def users_summary(
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """The three top cards on Manage Users: Total Customers / Shop Owners / Delivery Partners."""
    total_customers = await db.scalar(
        select(func.count()).select_from(Profile).where(Profile.role == "customer")
    )
    shop_owners = await db.scalar(
        select(func.count()).select_from(Profile).where(Profile.role == "shop_owner")
    )
    delivery_partners = await db.scalar(
        select(func.count()).select_from(Profile).where(Profile.role == "delivery_partner")
    )
    return {
        "total_customers": total_customers,
        "shop_owners": shop_owners,
        "delivery_partners": delivery_partners,
    }


@router.get("/shops", response_model=list[AdminShopOut])
async def list_all_shops(
    is_active: bool | None = Query(default=None),
    approval_status: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Case-insensitive substring match on shop name"),
    limit: int = Query(default=200, le=500),
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Unlike GET /shops (the public catalog), this deliberately does NOT
    filter to `is_active=True`/`approval_status="approved"` by default —
    an admin needs to see pending, rejected, and deactivated shops too
    (that's the whole point of the Manage Shops > Pending Approval tab),
    and this endpoint is low-traffic enough that Redis would add
    complexity with no real benefit.
    """
    if approval_status is not None and approval_status not in VALID_APPROVAL_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f'"{approval_status}" isn\'t a recognized status. Valid: {", ".join(VALID_APPROVAL_STATUSES)}',
        )

    stmt = (
        select(Shop, Profile.email, Profile.full_name, Address.city)
        .join(Profile, Profile.id == Shop.owner_id)
        .outerjoin(Address, Address.id == Shop.address_id)
    )
    if is_active is not None:
        stmt = stmt.where(Shop.is_active == is_active)
    if approval_status is not None:
        stmt = stmt.where(Shop.approval_status == approval_status)
    if q:
        stmt = stmt.where(Shop.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Shop.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    return [
        {
            "id": shop.id,
            "name": shop.name,
            "category": shop.category,
            "rating": shop.rating,
            "is_active": shop.is_active,
            "approval_status": shop.approval_status,
            "docs_status": shop.docs_status,
            "documents": shop.documents,
            "rejection_reason": shop.rejection_reason,
            "created_at": shop.created_at,
            "owner_id": shop.owner_id,
            "owner_email": owner_email,
            "owner_name": owner_name,
            "location": city,
        }
        for shop, owner_email, owner_name, city in result.all()
    ]


async def _shop_or_404(db: AsyncSession, shop_id: str) -> Shop:
    sid = parse_uuid_or_404(shop_id, "Shop")
    result = await db.execute(select(Shop).where(Shop.id == sid))
    shop = result.scalar_one_or_none()
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")
    return shop


async def _shop_out(db: AsyncSession, shop: Shop) -> dict:
    owner_result = await db.execute(select(Profile.email, Profile.full_name).where(Profile.id == shop.owner_id))
    owner_email, owner_name = owner_result.one()
    city = None
    if shop.address_id is not None:
        city = await db.scalar(select(Address.city).where(Address.id == shop.address_id))
    return {
        "id": shop.id,
        "name": shop.name,
        "category": shop.category,
        "rating": shop.rating,
        "is_active": shop.is_active,
        "approval_status": shop.approval_status,
        "docs_status": shop.docs_status,
        "documents": shop.documents,
        "rejection_reason": shop.rejection_reason,
        "created_at": shop.created_at,
        "owner_id": shop.owner_id,
        "owner_email": owner_email,
        "owner_name": owner_name,
        "location": city,
    }


@router.patch("/shops/{shop_id}/status", response_model=AdminShopOut)
async def update_shop_status(
    shop_id: str,
    payload: ShopStatusUpdate,
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    The platform-level moderation counterpart to a shop owner's own
    `PUT /dashboard/shops/{id}` — a shop owner can only edit their own
    shop's name/category/is_active (still gated by `_user_owns_shop`),
    while THIS endpoint lets an admin deactivate (or reactivate) ANY
    shop on the platform, e.g. in response to a complaint or a policy
    violation, independent of who owns it.
    """
    shop = await _shop_or_404(db, shop_id)

    old_status = shop.is_active
    shop.is_active = payload.is_active

    _record_audit(
        db,
        admin,
        action="shop_status_change",
        target_type="shop",
        target_id=shop.id,
        details={"shop_name": shop.name, "old_is_active": old_status, "new_is_active": payload.is_active},
    )

    await db.commit()
    await db.refresh(shop)

    # A shop an admin just deactivated must disappear from "Shops near
    # you" and product search immediately — not up to 60s later just
    # because Redis hasn't naturally expired the old cached value yet.
    await invalidate("shops:list", f"shop:{shop_id}", "categories:list")

    return await _shop_out(db, shop)


@router.patch("/shops/{shop_id}/approve", response_model=AdminShopOut)
async def approve_shop(
    shop_id: str,
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    "Approve Shop" in the Pending Approval queue. Flips BOTH
    approval_status -> "approved" and is_active -> True in one step
    (the mockup has no separate "approved but closed" state for a brand
    new application) — the shop goes live on the storefront the moment
    this returns. Also marks docs_status "verified" and clears any old
    rejection_reason — approving a shop IS the admin confirming its
    documents are in order.
    """
    shop = await _shop_or_404(db, shop_id)

    _record_audit(
        db,
        admin,
        action="shop_approved",
        target_type="shop",
        target_id=shop.id,
        details={"shop_name": shop.name},
    )

    shop.approval_status = "approved"
    shop.docs_status = "verified"
    shop.rejection_reason = None
    shop.is_active = True
    await db.commit()
    await db.refresh(shop)
    await invalidate("shops:list", f"shop:{shop_id}", "categories:list")
    return await _shop_out(db, shop)


@router.patch("/shops/{shop_id}/reject", response_model=AdminShopOut)
async def reject_shop(
    shop_id: str,
    payload: RejectShopRequest | None = None,
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    "Reject" in the Pending Approval queue — the shop stays in the
    database (so its owner can see why and fix it) but never goes live.
    The optional `reason` is what the owner sees on their Shop
    Dashboard's rejection screen — it's cleared automatically the moment
    they resubmit documents (see shop_dashboard.py's update_my_shop).
    """
    shop = await _shop_or_404(db, shop_id)

    reason = payload.reason if payload else None
    _record_audit(
        db,
        admin,
        action="shop_rejected",
        target_type="shop",
        target_id=shop.id,
        details={"shop_name": shop.name, "reason": reason},
    )

    shop.approval_status = "rejected"
    shop.is_active = False
    shop.rejection_reason = reason
    await db.commit()
    await db.refresh(shop)
    await invalidate("shops:list", f"shop:{shop_id}", "categories:list")
    return await _shop_out(db, shop)


@router.patch("/shops/{shop_id}/request-docs", response_model=AdminShopOut)
async def request_shop_docs(
    shop_id: str,
    payload: RejectShopRequest | None = None,
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    "Request Docs" in the Pending Approval queue — marks documents as
    needing (re)review, without touching the approval decision itself.
    Reuses RejectShopRequest's `reason` field to tell the owner what's
    missing/wrong (e.g. "GST certificate photo is unreadable") — shown on
    their Shop Dashboard the same way a rejection reason is.
    """
    shop = await _shop_or_404(db, shop_id)

    reason = payload.reason if payload else None
    _record_audit(
        db,
        admin,
        action="shop_docs_requested",
        target_type="shop",
        target_id=shop.id,
        details={"shop_name": shop.name, "reason": reason},
    )

    shop.docs_status = "pending"
    shop.rejection_reason = reason
    await db.commit()
    await db.refresh(shop)
    return await _shop_out(db, shop)


@router.get("/metrics", response_model=PlatformMetrics)
async def platform_metrics(
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Deliberately several small, independent COUNT/SUM queries rather than
    one giant joined query. These tables (profiles, shops, products,
    orders) aren't joined by any single key that would make a combined
    query meaningful without fan-out duplicating rows and skewing the
    counts (e.g. joining shops to orders would multiply the user count
    by however many orders each user's shop has). At this project's
    scale, running ~8 cheap indexed COUNT queries is simpler to read
    and verify correct than one query built around avoiding fan-out.
    """
    total_users = await db.scalar(select(func.count()).select_from(Profile))
    total_shop_owners = await db.scalar(
        select(func.count()).select_from(Profile).where(Profile.role == "shop_owner")
    )
    total_admins = await db.scalar(select(func.count()).select_from(Profile).where(Profile.role == "admin"))

    total_shops = await db.scalar(select(func.count()).select_from(Shop))
    active_shops = await db.scalar(select(func.count()).select_from(Shop).where(Shop.is_active.is_(True)))

    total_products = await db.scalar(select(func.count()).select_from(Product))
    active_products = await db.scalar(
        select(func.count()).select_from(Product).where(Product.is_active.is_(True))
    )

    total_orders = await db.scalar(select(func.count()).select_from(Order))
    # "confirmed" here means "a real, paid order that's part of the
    # fulfillment pipeline" — i.e. any status a paid order can be in
    # (confirmed/preparing/ready/delivered), not literally the single
    # status value "confirmed". Once an order moves past "confirmed" in
    # the shop dashboard it's still very much a sale; it just shouldn't
    # silently drop out of GMV/order counts because it progressed.
    confirmed_orders = await db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.status.in_(RECOGNIZED_ORDER_STATUSES))
    )
    gmv = await db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.status.in_(RECOGNIZED_ORDER_STATUSES)
        )
    )

    return {
        "total_users": total_users,
        "total_shop_owners": total_shop_owners,
        "total_admins": total_admins,
        "total_shops": total_shops,
        "active_shops": active_shops,
        "total_products": total_products,
        "active_products": active_products,
        "total_orders": total_orders,
        "confirmed_orders": confirmed_orders,
        "gmv": gmv,
    }


@router.get("/dashboard-summary", response_model=DashboardSummary)
async def dashboard_summary(
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """The four top cards on the Admin Panel's Dashboard tab, each with a period-over-period delta."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    this_month_start, next_month_start = _month_bounds(0)
    last_month_start, _ = _month_bounds(1)

    total_shops = await db.scalar(select(func.count()).select_from(Shop))
    shops_added_this_month = await db.scalar(
        select(func.count()).select_from(Shop).where(Shop.created_at >= this_month_start)
    )

    total_users = await db.scalar(select(func.count()).select_from(Profile))
    users_added_this_week = await db.scalar(
        select(func.count()).select_from(Profile).where(Profile.created_at >= week_ago)
    )

    orders_this_month = await db.scalar(
        select(func.count())
        .select_from(Order)
        .where(Order.status.in_(RECOGNIZED_ORDER_STATUSES), Order.created_at >= this_month_start)
    )
    orders_last_month = await db.scalar(
        select(func.count())
        .select_from(Order)
        .where(
            Order.status.in_(RECOGNIZED_ORDER_STATUSES),
            Order.created_at >= last_month_start,
            Order.created_at < this_month_start,
        )
    )

    revenue_this_month = await db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.status.in_(RECOGNIZED_ORDER_STATUSES), Order.created_at >= this_month_start
        )
    )
    revenue_last_month = await db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.status.in_(RECOGNIZED_ORDER_STATUSES),
            Order.created_at >= last_month_start,
            Order.created_at < this_month_start,
        )
    )

    def pct_change(current, previous) -> float | None:
        if not previous:
            return None
        return round((float(current) - float(previous)) / float(previous) * 100, 1)

    return {
        "total_shops": total_shops,
        "shops_added_this_month": shops_added_this_month,
        "total_users": total_users,
        "users_added_this_week": users_added_this_week,
        "monthly_orders": orders_this_month,
        "monthly_orders_change_pct": pct_change(orders_this_month, orders_last_month),
        "platform_revenue": revenue_this_month,
        "platform_revenue_change_pct": pct_change(revenue_this_month, revenue_last_month),
    }


@router.get("/revenue-trend", response_model=list[MonthPoint])
async def revenue_trend(
    months: int = Query(default=7, ge=1, le=24),
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """Platform Revenue line chart on the Dashboard tab: confirmed-order revenue per calendar month."""
    month_col = func.date_trunc("month", Order.created_at)
    stmt = (
        select(month_col.label("month"), func.coalesce(func.sum(Order.total_amount), 0))
        .where(
            Order.status.in_(RECOGNIZED_ORDER_STATUSES),
            Order.created_at >= _month_bounds(months - 1)[0],
        )
        .group_by(month_col)
        .order_by(month_col)
    )
    result = await db.execute(stmt)
    by_month = {row[0]: row[1] for row in result.all()}

    points = []
    for i in range(months - 1, -1, -1):
        start, _ = _month_bounds(i)
        points.append(MonthPoint(label=start.strftime("%b"), value=by_month.get(start, 0) or 0))
    return points


@router.get("/shop-growth", response_model=list[MonthPoint])
async def shop_growth(
    months: int = Query(default=7, ge=1, le=24),
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """Monthly Shop Growth bar chart on the Reports tab: new shops created per calendar month."""
    month_col = func.date_trunc("month", Shop.created_at)
    stmt = (
        select(month_col.label("month"), func.count())
        .where(Shop.created_at >= _month_bounds(months - 1)[0])
        .group_by(month_col)
        .order_by(month_col)
    )
    result = await db.execute(stmt)
    by_month = {row[0]: row[1] for row in result.all()}

    points = []
    for i in range(months - 1, -1, -1):
        start, _ = _month_bounds(i)
        points.append(MonthPoint(label=start.strftime("%b"), value=by_month.get(start, 0) or 0))
    return points


@router.get("/category-breakdown", response_model=list[CategoryShare])
async def category_breakdown(
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Powers BOTH the Dashboard's "Orders by Category" donut and the
    Reports tab's "Revenue by Category" pie — the mockup shows the same
    percentage breakdown in both places, so one endpoint (revenue share
    per shop category, across confirmed orders) backs both charts rather
    than computing two subtly different breakdowns that could drift.
    """
    stmt = (
        select(Shop.category, func.coalesce(func.sum(Order.total_amount), 0))
        .join(Shop, Shop.id == Order.shop_id)
        .where(Order.status.in_(RECOGNIZED_ORDER_STATUSES))
        .group_by(Shop.category)
    )
    result = await db.execute(stmt)
    rows = result.all()
    total = sum(float(amount) for _, amount in rows)
    if total <= 0:
        return []
    shares = sorted(
        ({"category": category, "pct": round(float(amount) / total * 100, 1)} for category, amount in rows),
        key=lambda r: r["pct"],
        reverse=True,
    )
    return shares


@router.get("/settings", response_model=PlatformSettingsOut)
async def get_settings(
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    settings_row = await db.get(PlatformSettings, 1)
    if settings_row is None:
        # Defensive fallback in case the seed row from the migration is
        # somehow missing — creates it on first read rather than 500ing.
        settings_row = PlatformSettings(
            id=1,
            payment_gateways=[
                {"key": "razorpay", "name": "Razorpay", "enabled": True, "primary": True},
                {"key": "upi_direct", "name": "UPI Direct", "enabled": True, "primary": False},
                {"key": "cod", "name": "Cash on Delivery", "enabled": True, "primary": False},
            ],
        )
        db.add(settings_row)
        await db.commit()
        await db.refresh(settings_row)
    return settings_row


@router.put("/settings", response_model=PlatformSettingsOut)
async def update_settings(
    payload: PlatformSettingsUpdate,
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Backs every "Edit" button on Settings > Platform Settings, plus the
    Payment Gateway toggles — each save sends only the field(s) that
    changed (see PlatformSettingsUpdate's docstring), so this applies
    whichever subset of fields is present rather than requiring the
    whole object every time.
    """
    settings_row = await db.get(PlatformSettings, 1)
    if settings_row is None:
        raise HTTPException(status_code=404, detail="Platform settings not initialized")

    updates = payload.model_dump(exclude_unset=True)
    gateways_changed = "payment_gateways" in updates
    for field, value in updates.items():
        if field == "payment_gateways":
            setattr(settings_row, field, [g.model_dump() if hasattr(g, "model_dump") else g for g in value])
        else:
            setattr(settings_row, field, value)

    _record_audit(
        db,
        admin,
        action="platform_settings_updated",
        target_type="platform_settings",
        target_id=None,
        details={"fields": list(updates.keys())},
    )

    await db.commit()
    await db.refresh(settings_row)
    return settings_row


@router.get("/audit-log", response_model=list[AuditLogOut])
async def list_audit_log(
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Newest first, paginated with a plain limit/offset — this table is
    append-only and admin-only traffic, nowhere near the scale where
    offset pagination's well-known slowness on deep pages would matter.
    """
    stmt = (
        select(AuditLog, Profile.email)
        .outerjoin(Profile, Profile.id == AuditLog.admin_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return [
        {
            "id": entry.id,
            "admin_email": admin_email,
            "action": entry.action,
            "target_type": entry.target_type,
            "target_id": entry.target_id,
            "details": entry.details,
            "created_at": entry.created_at,
        }
        for entry, admin_email in result.all()
    ]
