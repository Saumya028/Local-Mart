import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate
from app.core.db import get_db
from app.core.security import require_role
from app.core.utils import parse_uuid_or_404
from app.models import AuditLog, Order, Product, Profile, Shop
from app.schemas.admin import (
    VALID_ROLES,
    AdminShopOut,
    AdminUserOut,
    AuditLogOut,
    PlatformMetrics,
    RoleUpdate,
    ShopStatusUpdate,
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


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    role: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Case-insensitive substring match on email"),
    limit: int = Query(default=200, le=500),
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Profile)
    if role is not None:
        stmt = stmt.where(Profile.role == role)
    if q:
        stmt = stmt.where(Profile.email.ilike(f"%{q}%"))
    stmt = stmt.order_by(Profile.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    return result.scalars().all()


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
            detail="You can't change your own role from here — use scripts/promote_user.py if you really need to.",
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
    return user


@router.get("/shops", response_model=list[AdminShopOut])
async def list_all_shops(
    is_active: bool | None = Query(default=None),
    q: str | None = Query(default=None, description="Case-insensitive substring match on shop name"),
    limit: int = Query(default=200, le=500),
    admin: Profile = Depends(RequireAdmin),
    db: AsyncSession = Depends(get_db),
):
    """
    Unlike GET /shops (the public catalog), this deliberately does NOT
    filter to `is_active=True` by default and is NOT cached — an admin
    needs to see deactivated shops too (to reactivate them), and this
    endpoint is low-traffic enough that Redis would add complexity with
    no real benefit.
    """
    stmt = select(Shop, Profile.email).join(Profile, Profile.id == Shop.owner_id)
    if is_active is not None:
        stmt = stmt.where(Shop.is_active == is_active)
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
            "created_at": shop.created_at,
            "owner_id": shop.owner_id,
            "owner_email": owner_email,
        }
        for shop, owner_email in result.all()
    ]


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
    sid = parse_uuid_or_404(shop_id, "Shop")
    result = await db.execute(select(Shop).where(Shop.id == sid))
    shop = result.scalar_one_or_none()
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")

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

    owner_result = await db.execute(select(Profile.email).where(Profile.id == shop.owner_id))
    owner_email = owner_result.scalar_one()

    return {
        "id": shop.id,
        "name": shop.name,
        "category": shop.category,
        "rating": shop.rating,
        "is_active": shop.is_active,
        "created_at": shop.created_at,
        "owner_id": shop.owner_id,
        "owner_email": owner_email,
    }


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
    confirmed_orders = await db.scalar(
        select(func.count()).select_from(Order).where(Order.status == "confirmed")
    )
    gmv = await db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(Order.status == "confirmed")
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
