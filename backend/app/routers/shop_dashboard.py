import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.attribute_validation import validate_attributes
from app.core.cache import invalidate
from app.core.db import get_db
from app.core.order_status import (
    DELIVERY_PROOF_REQUIRED_STATUSES,
    RECOGNIZED_STATUSES,
    TERMINAL_STATUSES,
    allowed_transitions_for,
)
from app.core.return_status import SHOP_ALLOWED_TRANSITIONS
from app.core.security import require_role
from app.core.supabase_admin import (
    create_supabase_user,
    delete_supabase_user,
    update_supabase_user_password,
)
from app.core.utils import parse_uuid_or_404
from app.models import Order, OrderItem, Product, Profile, ReturnRequest, Shop
from app.schemas.dashboard import (
    AnalyticsOut,
    DashboardMetrics,
    DayPoint,
    RecentOrderPreview,
    TopProductOut,
)
from app.schemas.order import DashboardOrderOut, OrderStatusUpdate
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.schemas.return_request import ReturnRequestOut, ReturnStatusUpdate
from app.schemas.shop import DashboardShopOut, ShopUpdate
from app.schemas.staff import StaffCreate, StaffOut, StaffUpdate

# Roles allowed to reach the SHARED, shop-scoped parts of this dashboard
# (products/inventory, returns, orders, analytics) beyond the owner —
# see individual endpoints below for which of these three actually apply
# per endpoint. Staff management itself (/dashboard/staff) stays
# shop_owner/admin only, never listed here. "delivery_partner" (not
# "delivery") to match the role name app/schemas/admin.py's VALID_ROLES
# already reserved for this concept.
STAFF_ROLES = ("manager", "delivery_partner")

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# See app/core/order_status.py for the two transition tables (delivery
# vs. pickup) and the "recognized" (paid) statuses — both are shared
# with admin.py so platform-wide metrics and this dashboard never drift
# apart on what counts as a real sale. Note in particular: neither table
# has an entry leading to "cancelled" anywhere — there is no
# reject/cancel action a shop owner can take here, by design. The only
# forward path is confirmed ("Pending" in the UI) -> preparing ->
# packing -> out_for_delivery -> delivered (delivery) or -> packing ->
# ready_for_pickup -> picked_up (pickup).

DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _today_start_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _bucket_by_day(
    rows: list[tuple[datetime, str, Decimal]], window_start: datetime, num_days: int
) -> tuple[list[Decimal], list[int]]:
    """Buckets (created_at, status, total_amount) rows into `num_days`
    daily slots starting at `window_start`. Returns (revenue_per_day,
    orders_per_day) — revenue only counts RECOGNIZED_STATUSES, order
    counts include every status (a shop still wants to see failed/
    abandoned attempts show up as "an order happened that day")."""
    revenue = [Decimal("0")] * num_days
    orders = [0] * num_days
    for created_at, status, total_amount in rows:
        offset = (created_at - window_start).days
        if 0 <= offset < num_days:
            orders[offset] += 1
            if status in RECOGNIZED_STATUSES:
                revenue[offset] += total_amount
    return revenue, orders


def _user_owns_shop(shop: Shop | None, user: Profile) -> bool:
    """
    The one authorization check every mutating endpoint in this file
    relies on. Pulled out as its own function (rather than inlined
    everywhere) specifically so it's independently unit-testable without
    needing a live database — see backend tests for the exact race/auth
    checks this project verifies before shipping.
    """
    return shop is not None and (shop.owner_id == user.id or user.role == "admin")


async def _get_owned_shop_ids(user_id: uuid.UUID, db: AsyncSession) -> list[uuid.UUID]:
    result = await db.execute(select(Shop.id).where(Shop.owner_id == user_id))
    return [row[0] for row in result.all()]


async def _get_owned_shop_or_403(shop_id: uuid.UUID, user: Profile, db: AsyncSession) -> Shop:
    result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = result.scalar_one_or_none()
    if not _user_owns_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't own this shop")
    return shop


def _user_can_manage_shop(shop: Shop | None, user: Profile) -> bool:
    """
    The broader counterpart to `_user_owns_shop` above, for every
    endpoint a manager/delivery staff member should ALSO be able to
    reach (products, inventory, orders, returns, analytics — never shop
    settings or staff management, which stay `_user_owns_shop`-gated).
    A staff profile's single shop lives on `Profile.shop_id` (see
    models/profile.py) — set once, at account creation, never something
    the staff member edits themselves.
    """
    if shop is None:
        return False
    if user.role == "admin" or shop.owner_id == user.id:
        return True
    return user.role in STAFF_ROLES and user.shop_id == shop.id


async def _get_accessible_shop_ids(user: Profile, db: AsyncSession) -> list[uuid.UUID] | None:
    """
    The staff-aware counterpart to `_get_owned_shop_ids` — returns None
    for admin (meaning "no filter, sees everything", matching every
    existing `owned_shop_ids is None` check below), a shop_owner's own
    shops for that role, and the single assigned shop (or none at all)
    for a manager/delivery staff member.
    """
    if user.role == "admin":
        return None
    if user.role == "shop_owner":
        return await _get_owned_shop_ids(user.id, db)
    return [user.shop_id] if user.shop_id is not None else []


async def _get_accessible_shop_or_403(shop_id: uuid.UUID, user: Profile, db: AsyncSession) -> Shop:
    result = await db.execute(select(Shop).where(Shop.id == shop_id))
    shop = result.scalar_one_or_none()
    if not _user_can_manage_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't have access to this shop")
    return shop


def _require_approved_shop(shop: Shop) -> None:
    """
    THE fix for the real gap a test run surfaced: previously nothing
    stopped a shop owner from fully operating a shop (adding products,
    the works) the instant POST /shops returned — regardless of
    approval_status, which is meaningless if nothing actually checks it.
    Every mutating, shop-scoped action below calls this right after
    `_user_owns_shop` passes. Deliberately NOT applied to `my_shops` or
    `update_my_shop` — an owner still needs to see their pending/rejected
    shop's status and resubmit documents on it (see ShopUpdate.documents),
    which would be impossible if this blocked that endpoint too.
    """
    if shop.approval_status != "approved":
        detail = {
            "pending": "This shop is still awaiting admin approval. You can manage it once it's approved.",
            "rejected": "This shop's application was rejected. Update its documents and it will be reviewed again.",
        }.get(shop.approval_status, "This shop isn't approved yet.")
        raise HTTPException(status_code=403, detail=detail)


@router.get("/shops", response_model=list[DashboardShopOut])
async def my_shops(
    user: Profile = Depends(require_role("shop_owner", "admin", *STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """
    Requires role="shop_owner"/"admin"/"manager"/"delivery_partner" — this is a
    deliberate access gate, not just ownership scoping. Becoming a
    shop_owner is an explicit promotion (self-service application) and
    becoming staff is an explicit action too (a shop owner creating them
    via POST /dashboard/staff) — neither is something a plain customer
    account can trigger itself. The frontend checks the user's role
    BEFORE ever calling this endpoint (see the Shop Dashboard page), so a
    customer never even reaches the point of getting a 403 here in
    normal use — but the backend enforces it regardless, since the
    frontend check alone is never the real security boundary.

    Returns DashboardShopOut (not the public ShopOut) — an owner (or
    their staff) genuinely needs to see approval_status/docs_status/
    rejection_reason to know what state the shop's application is in.
    A manager/delivery account sees exactly the one shop they're
    assigned to (via Profile.shop_id), never every shop a customer would
    see on the public catalog.
    """
    if user.role in STAFF_ROLES:
        if user.shop_id is None:
            return []
        result = await db.execute(select(Shop).where(Shop.id == user.shop_id))
    else:
        # Unchanged from before this feature: shop_owner sees the shops
        # they own; admin's own behavior here is untouched too (admin
        # oversight of every shop happens via /admin/*, not this
        # endpoint — this stays scoped to owner_id even for an admin
        # caller, exactly as it already was).
        result = await db.execute(select(Shop).where(Shop.owner_id == user.id))
    return result.scalars().all()


@router.put("/shops/{shop_id}", response_model=DashboardShopOut)
async def update_my_shop(
    shop_id: str,
    payload: ShopUpdate,
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Deliberately NOT gated by _require_approved_shop — this is exactly
    how a pending or rejected shop's owner resubmits documents (see
    ShopUpdate.documents) or fixes its name/category, which has to keep
    working precisely WHILE the shop isn't approved yet.
    """
    sid = parse_uuid_or_404(shop_id, "Shop")
    result = await db.execute(select(Shop).where(Shop.id == sid))
    shop = result.scalar_one_or_none()

    if not _user_owns_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't own this shop")

    updates = payload.model_dump(exclude_unset=True)
    if "documents" in updates:
        # Resubmitting documents is itself the action that puts the
        # application back in the admin's queue — flip docs_status back
        # to "submitted" and clear whatever the previous rejection said,
        # rather than making the owner wait on a second, separate call.
        shop.docs_status = "submitted"
        shop.rejection_reason = None
        if shop.approval_status == "rejected":
            shop.approval_status = "pending"

    if "attributes" in updates or "category" in updates:
        merged_category = updates.get("category", shop.category)
        merged_attributes = updates.get("attributes", shop.attributes)
        await validate_attributes(db, "shop", merged_category, merged_attributes)

    for key, value in updates.items():
        setattr(shop, key, value)

    await db.commit()
    await db.refresh(shop)

    await invalidate("shops:list", f"shop:{shop_id}")
    return shop


@router.post("/products", response_model=ProductOut)
async def create_product(
    payload: ProductCreate,
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    shop_result = await db.execute(select(Shop).where(Shop.id == payload.shop_id))
    shop = shop_result.scalar_one_or_none()

    # The `shop_id` in the request body is NEVER trusted by itself — this
    # is the check that stops a shop owner (or their manager) from
    # creating a product under a shop they don't own/work for just by
    # knowing (or guessing) its ID.
    if not _user_can_manage_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't have access to this shop")
    _require_approved_shop(shop)
    # Category-specific required fields (e.g. Pharmacy's
    # prescription_required) live in AttributeSchema, defined by an
    # admin — see core/attribute_validation.py.
    await validate_attributes(db, "product", payload.category, payload.attributes)

    variant_group_id = None
    variant_attributes: dict = {}
    if payload.variant_of_product_id is not None:
        sibling_result = await db.execute(select(Product).where(Product.id == payload.variant_of_product_id))
        sibling = sibling_result.scalar_one_or_none()
        # Same ownership check as `shop` above — a shop owner can only
        # ever group a new product with one of THEIR OWN existing
        # products, never a competitor's, no matter what id they send.
        if sibling is None or sibling.shop_id != shop.id:
            raise HTTPException(
                status_code=404, detail="variant_of_product_id must be one of your own products"
            )
        if sibling.variant_group_id is None:
            # First variant added to a previously-standalone product —
            # promote it into a group of its own rather than requiring
            # the seller to have planned for variants up front.
            sibling.variant_group_id = uuid.uuid4()
        variant_group_id = sibling.variant_group_id
        variant_attributes = payload.variant_attributes

    product_data = payload.model_dump(exclude={"variant_of_product_id", "variant_attributes"})
    product = Product(
        id=uuid.uuid4(),
        variant_group_id=variant_group_id,
        variant_attributes=variant_attributes,
        **product_data,
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)

    await invalidate("categories:list")
    return product


@router.get("/products", response_model=list[ProductOut])
async def my_products(
    shop_id: uuid.UUID | None = Query(default=None),
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    accessible_shop_ids = await _get_accessible_shop_ids(user, db)

    stmt = select(Product)
    if shop_id is not None:
        stmt = stmt.where(Product.shop_id == shop_id)
    if accessible_shop_ids is not None:
        stmt = stmt.where(Product.shop_id.in_(accessible_shop_ids))

    result = await db.execute(stmt.order_by(Product.created_at.desc()))
    return result.scalars().all()


async def _get_owned_product_or_403(product_id: str, user: Profile, db: AsyncSession) -> Product:
    pid = parse_uuid_or_404(product_id, "Product")
    result = await db.execute(select(Product).where(Product.id == pid))
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    shop_result = await db.execute(select(Shop).where(Shop.id == product.shop_id))
    shop = shop_result.scalar_one_or_none()
    if not _user_can_manage_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't have access to this product")
    _require_approved_shop(shop)

    return product


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    product = await _get_owned_product_or_403(product_id, user, db)

    updates = payload.model_dump(exclude_unset=True)
    # Validate against the resulting state, not just what changed — a
    # partial update ("just changing the price") still needs to satisfy
    # the CURRENT category's required fields, in case the category
    # itself changed in this same request or a schema was tightened
    # since the product was created.
    if "attributes" in updates or "category" in updates:
        merged_category = updates.get("category", product.category)
        merged_attributes = updates.get("attributes", product.attributes)
        await validate_attributes(db, "product", merged_category, merged_attributes)

    for key, value in updates.items():
        setattr(product, key, value)

    await db.commit()
    await db.refresh(product)

    # The customer-facing product page AND the category counts are both
    # cached — a price/stock/active-status change here must not stay
    # invisible to shoppers for up to a minute just because Redis hasn't
    # naturally expired the old value yet.
    await invalidate(f"product:{product_id}", "categories:list")
    return product


@router.delete("/products/{product_id}")
async def deactivate_product(
    product_id: str,
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """
    Deactivates rather than hard-deletes. A real DELETE would violate the
    RESTRICT foreign key from order_items the moment anyone has ever
    bought this product — and even before that first sale, keeping a
    discontinued product's history around is generally what sellers
    actually want. This is exactly the `is_active` flag the rest of the
    catalog (search, product detail) already respects.
    """
    product = await _get_owned_product_or_403(product_id, user, db)
    product.is_active = False
    await db.commit()

    await invalidate(f"product:{product_id}", "categories:list")
    return {"id": product_id, "deactivated": True}


@router.get("/orders", response_model=list[DashboardOrderOut])
async def incoming_orders(
    shop_id: uuid.UUID | None = Query(default=None),
    user: Profile = Depends(require_role("shop_owner", "admin", *STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    accessible_shop_ids = await _get_accessible_shop_ids(user, db)

    item_counts = (
        select(OrderItem.order_id, func.sum(OrderItem.quantity).label("item_count"))
        .group_by(OrderItem.order_id)
        .subquery()
    )

    stmt = (
        select(Order, Profile.email, Profile.full_name, item_counts.c.item_count)
        .join(Profile, Profile.id == Order.user_id)
        .outerjoin(item_counts, item_counts.c.order_id == Order.id)
    )
    if shop_id is not None:
        stmt = stmt.where(Order.shop_id == shop_id)
    if accessible_shop_ids is not None:
        stmt = stmt.where(Order.shop_id.in_(accessible_shop_ids))

    result = await db.execute(stmt.order_by(Order.created_at.desc()))
    return [
        {
            "id": order.id,
            "shop_id": order.shop_id,
            "status": order.status,
            "fulfillment_type": order.fulfillment_type,
            "total_amount": order.total_amount,
            "delivery_address": order.delivery_address,
            "created_at": order.created_at,
            "buyer_email": buyer_email,
            "buyer_name": buyer_name,
            "item_count": int(item_count or 0),
            "delivered_at": order.delivered_at,
            "delivery_proof_photo_url": order.delivery_proof_photo_url,
        }
        for order, buyer_email, buyer_name, item_count in result.all()
    ]


@router.patch("/orders/{order_id}/status", response_model=DashboardOrderOut)
async def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    user: Profile = Depends(require_role("shop_owner", "admin", *STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    oid = parse_uuid_or_404(order_id, "Order")
    result = await db.execute(select(Order).where(Order.id == oid))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    shop_result = await db.execute(select(Shop).where(Shop.id == order.shop_id))
    shop = shop_result.scalar_one_or_none()
    if not _user_can_manage_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't have access to this order")
    _require_approved_shop(shop)

    allowed_next = allowed_transitions_for(order.fulfillment_type).get(order.status, set())
    if payload.status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f'Cannot move an order from "{order.status}" to "{payload.status}"',
        )

    if payload.status in DELIVERY_PROOF_REQUIRED_STATUSES and not (
        payload.delivery_proof_photo_url and payload.delivery_proof_photo_url.strip()
    ):
        raise HTTPException(
            status_code=400,
            detail="A photo of the delivered order is required to mark it as delivered.",
        )

    order.status = payload.status
    if payload.delivery_proof_photo_url:
        order.delivery_proof_photo_url = payload.delivery_proof_photo_url
    if payload.status in TERMINAL_STATUSES:
        # Stamped here, once, the moment the order actually reaches
        # EITHER terminal status ("delivered" or "picked_up") — this is
        # what the return/exchange window (app/core/return_status.py's
        # RETURN_WINDOW) counts from. Using created_at instead would
        # unfairly shrink a customer's return window by however long the
        # order took to actually reach them.
        order.delivered_at = datetime.now(timezone.utc)
    await db.commit()

    buyer_result = await db.execute(
        select(Profile.email, Profile.full_name).where(Profile.id == order.user_id)
    )
    buyer_email, buyer_name = buyer_result.one()

    item_count_result = await db.execute(
        select(func.coalesce(func.sum(OrderItem.quantity), 0)).where(
            OrderItem.order_id == order.id
        )
    )
    item_count = item_count_result.scalar_one()

    return {
        "id": order.id,
        "shop_id": order.shop_id,
        "status": order.status,
        "fulfillment_type": order.fulfillment_type,
        "total_amount": order.total_amount,
        "delivery_address": order.delivery_address,
        "created_at": order.created_at,
        "buyer_email": buyer_email,
        "buyer_name": buyer_name,
        "item_count": int(item_count),
        "delivered_at": order.delivered_at,
        "delivery_proof_photo_url": order.delivery_proof_photo_url,
    }


@router.get("/summary")
async def sales_summary(
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """
    Paid-orders-only revenue per shop — a "pending" order hasn't actually
    been paid for yet, and a "payment_failed" one never will be, so
    neither should count toward sales. "Paid" here means any status a
    paid order can be in (confirmed/preparing/packing/out_for_delivery/
    delivered) — see app/core/order_status.py. One GROUP BY query for
    however many shops the user (or, for a manager, their one assigned
    shop) can access, rather than one query per shop.
    """
    accessible_shop_ids = await _get_accessible_shop_ids(user, db)

    stmt = (
        select(
            Shop.id,
            Shop.name,
            func.count(Order.id).filter(Order.status.in_(RECOGNIZED_STATUSES)),
            func.coalesce(
                func.sum(Order.total_amount).filter(Order.status.in_(RECOGNIZED_STATUSES)), 0
            ),
        )
        .select_from(Shop)
        .outerjoin(Order, Order.shop_id == Shop.id)
    )
    if accessible_shop_ids is not None:
        stmt = stmt.where(Shop.id.in_(accessible_shop_ids))
    stmt = stmt.group_by(Shop.id, Shop.name)

    result = await db.execute(stmt)
    return [
        {
            "shop_id": str(shop_id),
            "shop_name": shop_name,
            "confirmed_orders": count,
            "revenue": str(revenue),
        }
        for shop_id, shop_name, count, revenue in result.all()
    ]


@router.get("/metrics", response_model=DashboardMetrics)
async def dashboard_metrics(
    shop_id: uuid.UUID = Query(...),
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """Powers the Dashboard home tab: today's headline numbers, the
    7-day revenue chart, top products, and a short recent-orders list —
    all scoped to one shop the requesting user (owner or their manager)
    can actually access."""
    shop = await _get_accessible_shop_or_403(shop_id, user, db)

    today_start = _today_start_utc()
    yesterday_start = today_start - timedelta(days=1)
    week_start = today_start - timedelta(days=6)  # 7 days total, including today
    prev_week_start = week_start - timedelta(days=7)

    week_rows_result = await db.execute(
        select(Order.created_at, Order.status, Order.total_amount).where(
            Order.shop_id == shop_id, Order.created_at >= week_start
        )
    )
    week_rows = week_rows_result.all()
    revenue_by_day, _orders_by_day = _bucket_by_day(week_rows, week_start, 7)

    today_revenue = revenue_by_day[6]
    yesterday_revenue = revenue_by_day[5]
    today_orders = sum(
        1
        for created_at, status, _ in week_rows
        if created_at >= today_start and status in RECOGNIZED_STATUSES
    )
    yesterday_orders = sum(
        1
        for created_at, status, _ in week_rows
        if yesterday_start <= created_at < today_start and status in RECOGNIZED_STATUSES
    )

    prev_week_result = await db.execute(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.shop_id == shop_id,
            Order.created_at >= prev_week_start,
            Order.created_at < week_start,
            Order.status.in_(RECOGNIZED_STATUSES),
        )
    )
    prev_week_revenue = prev_week_result.scalar_one()
    week_revenue_total = sum(revenue_by_day, Decimal("0"))
    week_change_pct = (
        float((week_revenue_total - prev_week_revenue) / prev_week_revenue * 100)
        if prev_week_revenue
        else None
    )

    pending_result = await db.execute(
        select(func.count()).where(Order.shop_id == shop_id, Order.status == "confirmed")
    )
    pending_orders = pending_result.scalar_one()

    urgent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    urgent_result = await db.execute(
        select(func.count()).where(
            Order.shop_id == shop_id,
            Order.status == "confirmed",
            Order.created_at < urgent_cutoff,
        )
    )
    urgent_pending_orders = urgent_result.scalar_one()

    top_products_result = await db.execute(
        select(
            Product.id,
            Product.name,
            func.sum(OrderItem.quantity),
            func.sum(OrderItem.quantity * OrderItem.unit_price),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(Order.shop_id == shop_id, Order.status.in_(RECOGNIZED_STATUSES))
        .group_by(Product.id, Product.name)
        .order_by(func.sum(OrderItem.quantity * OrderItem.unit_price).desc())
        .limit(4)
    )
    top_products = [
        TopProductOut(id=str(pid), name=name, units_sold=int(units), revenue=revenue)
        for pid, name, units, revenue in top_products_result.all()
    ]

    item_counts = (
        select(OrderItem.order_id, func.sum(OrderItem.quantity).label("item_count"))
        .group_by(OrderItem.order_id)
        .subquery()
    )
    recent_result = await db.execute(
        select(Order, Profile.email, Profile.full_name, item_counts.c.item_count)
        .join(Profile, Profile.id == Order.user_id)
        .outerjoin(item_counts, item_counts.c.order_id == Order.id)
        .where(Order.shop_id == shop_id)
        .order_by(Order.created_at.desc())
        .limit(4)
    )
    recent_orders = [
        RecentOrderPreview(
            id=str(order.id),
            buyer_name=buyer_name,
            buyer_email=buyer_email,
            item_count=int(item_count or 0),
            total_amount=order.total_amount,
            status=order.status,
            created_at=order.created_at.isoformat(),
        )
        for order, buyer_email, buyer_name, item_count in recent_result.all()
    ]

    revenue_points = [
        DayPoint(
            label=DAY_LABELS[(week_start + timedelta(days=i)).weekday()],
            date=(week_start + timedelta(days=i)).date().isoformat(),
            value=revenue_by_day[i],
        )
        for i in range(7)
    ]

    return DashboardMetrics(
        today_revenue=today_revenue,
        today_orders=today_orders,
        yesterday_revenue=yesterday_revenue,
        yesterday_orders=yesterday_orders,
        pending_orders=pending_orders,
        urgent_pending_orders=urgent_pending_orders,
        avg_rating=shop.rating,
        week_revenue_total=week_revenue_total,
        week_revenue_change_pct=week_change_pct,
        revenue_by_day=revenue_points,
        top_products=top_products,
        recent_orders=recent_orders,
    )


@router.get("/analytics", response_model=AnalyticsOut)
async def dashboard_analytics(
    shop_id: uuid.UUID = Query(...),
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """Powers the Analytics tab: all-time totals plus 7-day order-count
    and revenue trend series, scoped to one accessible shop."""
    await _get_accessible_shop_or_403(shop_id, user, db)

    totals_result = await db.execute(
        select(
            func.coalesce(
                func.sum(Order.total_amount).filter(Order.status.in_(RECOGNIZED_STATUSES)), 0
            ),
            func.count(Order.id),
            func.count(func.distinct(Order.user_id)),
            func.count(Order.id).filter(Order.status.in_(RECOGNIZED_STATUSES)),
        ).where(Order.shop_id == shop_id)
    )
    total_revenue, total_orders, unique_customers, recognized_orders = totals_result.one()
    conversion_rate_pct = (
        float(recognized_orders) / float(total_orders) * 100 if total_orders else 0.0
    )

    today_start = _today_start_utc()
    week_start = today_start - timedelta(days=6)
    week_rows_result = await db.execute(
        select(Order.created_at, Order.status, Order.total_amount).where(
            Order.shop_id == shop_id, Order.created_at >= week_start
        )
    )
    revenue_by_day, orders_by_day = _bucket_by_day(week_rows_result.all(), week_start, 7)

    orders_points = [
        DayPoint(
            label=DAY_LABELS[(week_start + timedelta(days=i)).weekday()],
            date=(week_start + timedelta(days=i)).date().isoformat(),
            value=Decimal(orders_by_day[i]),
        )
        for i in range(7)
    ]
    revenue_points = [
        DayPoint(
            label=DAY_LABELS[(week_start + timedelta(days=i)).weekday()],
            date=(week_start + timedelta(days=i)).date().isoformat(),
            value=revenue_by_day[i],
        )
        for i in range(7)
    ]

    return AnalyticsOut(
        total_revenue=total_revenue,
        total_orders=total_orders,
        unique_customers=unique_customers,
        conversion_rate_pct=round(conversion_rate_pct, 1),
        orders_by_day=orders_points,
        revenue_by_day=revenue_points,
    )


def _serialize_return(rr: ReturnRequest, **extra) -> dict:
    data = ReturnRequestOut.model_validate(rr).model_dump(mode="json")
    data.update(extra)
    return data


@router.get("/returns", response_model=list[ReturnRequestOut])
async def incoming_returns(
    shop_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """
    Return/exchange requests opened against this shop owner's own shop(s)
    (or every shop, for an admin; or the one assigned shop, for a
    manager) — the shop-side counterpart to routers/returns.py's
    customer-facing endpoints.
    """
    accessible_shop_ids = await _get_accessible_shop_ids(user, db)

    stmt = (
        select(ReturnRequest, Product.name, Profile.email, Profile.full_name)
        .join(OrderItem, OrderItem.id == ReturnRequest.order_item_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Profile, Profile.id == ReturnRequest.user_id)
    )
    if shop_id is not None:
        stmt = stmt.where(ReturnRequest.shop_id == shop_id)
    if accessible_shop_ids is not None:
        stmt = stmt.where(ReturnRequest.shop_id.in_(accessible_shop_ids))
    if status_filter is not None:
        stmt = stmt.where(ReturnRequest.status == status_filter)

    result = await db.execute(stmt.order_by(ReturnRequest.created_at.desc()))
    return [
        _serialize_return(rr, product_name=pname, buyer_email=email, buyer_name=name)
        for rr, pname, email, name in result.all()
    ]


@router.patch("/returns/{return_id}/status", response_model=ReturnRequestOut)
async def update_return_status(
    return_id: str,
    payload: ReturnStatusUpdate,
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """
    A shop owner's (or their manager's) response to one return/exchange
    request:

    - "approved": accepts the request — the customer is told to hand the
      item back (in person, or via whatever pickup process the shop
      arranges outside this app for now).
    - "rejected": declines it. Requires a non-empty `shop_note` so the
      customer always sees why, the same way a shop owner suspending a
      user (admin.py) or rejecting a shop's documents always requires a
      reason.
    - "completed": confirms the item was actually returned and resolves
      it — this is the one step that touches stock and, for an exchange,
      creates a new order:
        * "return": the returned quantity goes back into the ORIGINAL
          product's stock_qty (it's sellable again).
        * "exchange": the original quantity is restocked exactly like a
          return, the replacement product's stock is atomically reserved
          (the same race-safe UPDATE ... WHERE stock_qty >= qty used at
          checkout in routers/orders.py — 409 if it's since sold out,
          leaving the request "approved" so the shop can retry or
          reject instead), and a brand-new Order + OrderItem is created
          for that replacement item, starting at "confirmed" so it flows
          through the shop's normal fulfillment pipeline just like any
          other order. If the replacement costs more than the original
          (ReturnRequest.price_difference > 0), the customer must have
          already paid that top-up — via
          POST /returns/{id}/difference-payment — before this is allowed
          to complete; a shop owner can't be left holding a costlier item
          with no way to collect the difference.

    No live payment-gateway refund call happens here for the REFUND side
    of things — Payment (app/models/payment.py) only stores the Razorpay
    ORDER id, not the individual payment id a refund API call needs, so
    wiring up an actual Razorpay refund (or settling a negative
    price_difference — a cheaper replacement, where the shop owes money
    back) is future work; "completed" records that it was settled
    through whatever process the shop uses today (UPI, bank transfer,
    cash) and is the number that should reconcile against it.
    """
    rr_result = await db.execute(select(ReturnRequest).where(ReturnRequest.id == parse_uuid_or_404(return_id, "Return request")))
    rr = rr_result.scalar_one_or_none()
    if rr is None:
        raise HTTPException(status_code=404, detail="Return request not found")

    shop = await _get_accessible_shop_or_403(rr.shop_id, user, db)
    _require_approved_shop(shop)

    allowed_next = SHOP_ALLOWED_TRANSITIONS.get(rr.status, set())
    if payload.status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f'Cannot move a return request from "{rr.status}" to "{payload.status}"',
        )

    if payload.status == "rejected" and not (payload.shop_note and payload.shop_note.strip()):
        raise HTTPException(status_code=400, detail="A note explaining the rejection is required")

    new_order: Order | None = None

    if payload.status == "completed":
        if rr.request_type == "exchange" and rr.price_difference > 0 and not rr.difference_paid:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"The customer still owes ₹{rr.price_difference} for this exchange — "
                    "this can't be completed until they've paid it"
                ),
            )

        item_result = await db.execute(select(OrderItem).where(OrderItem.id == rr.order_item_id))
        order_item = item_result.scalar_one_or_none()
        if order_item is not None:
            await db.execute(
                update(Product)
                .where(Product.id == order_item.product_id)
                .values(stock_qty=Product.stock_qty + rr.quantity)
            )

        if rr.request_type == "exchange" and rr.exchange_product_id is not None:
            # Reserve stock and read back the current price in the same
            # atomic statement — same race-safe pattern checkout uses in
            # routers/orders.py — so the new Order below is priced off
            # exactly the stock we actually reserved, not a stale read
            # from before this UPDATE.
            reserve_stmt = (
                update(Product)
                .where(Product.id == rr.exchange_product_id, Product.stock_qty >= rr.quantity)
                .values(stock_qty=Product.stock_qty - rr.quantity)
                .returning(Product.id, Product.price)
            )
            reserved = await db.execute(reserve_stmt)
            reserved_row = reserved.first()
            if reserved_row is None:
                raise HTTPException(
                    status_code=409,
                    detail="The replacement item no longer has enough stock for this exchange",
                )
            _, exchange_price = reserved_row

            # The user's ask: an exchange isn't just a stock swap, it's a
            # NEW order for the replacement item — so it shows up in the
            # customer's Orders and the shop's Orders/dashboard exactly
            # like anything else they bought, and rides the same
            # confirmed -> preparing -> packing -> out_for_delivery -> delivered pipeline
            # (routers/shop_dashboard.py's update_order_status) instead of
            # needing its own parallel fulfillment tracking. Starts at
            # "confirmed" rather than "pending": there's no separate
            # payment to wait on here — the original purchase, plus
            # whatever top-up difference was required, is already
            # settled by this point.
            original_order_result = await db.execute(select(Order).where(Order.id == rr.order_id))
            original_order = original_order_result.scalar_one_or_none()
            delivery_address = original_order.delivery_address if original_order else ""

            new_order = Order(
                id=uuid.uuid4(),
                user_id=rr.user_id,
                shop_id=rr.shop_id,
                status="confirmed",
                total_amount=exchange_price * rr.quantity,
                delivery_address=delivery_address,
            )
            db.add(new_order)
            await db.flush()
            db.add(
                OrderItem(
                    id=uuid.uuid4(),
                    order_id=new_order.id,
                    product_id=rr.exchange_product_id,
                    quantity=rr.quantity,
                    unit_price=exchange_price,
                )
            )
            rr.new_order_id = new_order.id

    rr.status = payload.status
    if payload.shop_note is not None:
        rr.shop_note = payload.shop_note
    if payload.status in ("rejected", "completed"):
        rr.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(rr)

    product_result = await db.execute(
        select(Product.name).join(OrderItem, OrderItem.product_id == Product.id).where(
            OrderItem.id == rr.order_item_id
        )
    )
    product_name = product_result.scalar_one_or_none()

    buyer_result = await db.execute(
        select(Profile.email, Profile.full_name).where(Profile.id == rr.user_id)
    )
    buyer_email, buyer_name = buyer_result.one()

    return _serialize_return(rr, product_name=product_name, buyer_email=buyer_email, buyer_name=buyer_name)


# ---------------------------------------------------------------------
# Staff (manager/delivery) account management — shop_owner/admin only.
# See app/core/supabase_admin.py for the actual Supabase Admin API calls
# and app/models/profile.py's `shop_id` column for how a staff member is
# tied to exactly one shop.
# ---------------------------------------------------------------------


@router.get("/staff", response_model=list[StaffOut])
async def list_staff(
    shop_id: uuid.UUID = Query(...),
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Everyone (manager + delivery) currently assigned to one shop the
    caller owns. A removed staff member's profile row is gone (see
    remove_staff below), so this never shows anyone who no longer has
    any relationship to the shop."""
    await _get_owned_shop_or_403(shop_id, user, db)

    result = await db.execute(
        select(Profile)
        .where(Profile.shop_id == shop_id, Profile.role.in_(STAFF_ROLES))
        .order_by(Profile.created_at.desc())
    )
    return result.scalars().all()


@router.post("/staff", response_model=StaffOut)
async def create_staff(
    payload: StaffCreate,
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a real, working login for a manager or delivery person —
    not just a database row. Order matters here: the Supabase Auth user
    is created FIRST (see core/supabase_admin.py); the local `profiles`
    row is only inserted once that succeeds, using the SAME id Supabase
    just issued (exactly how every other account's profile row is keyed
    — see security.py's get_current_user). If the local insert then
    failed for some reason, we'd have an orphaned Supabase login with no
    app-side profile; the `except` below cleans that up rather than
    leaving a half-created account behind.

    Deliberately does NOT go through get_current_user's normal
    auto-provision path — that path always defaults a brand-new profile
    to role="customer", which would be wrong here on purpose: this
    profile needs to start life already scoped to a shop and a role.
    """
    shop = await _get_owned_shop_or_403(payload.shop_id, user, db)
    _require_approved_shop(shop)

    existing = await db.execute(select(Profile).where(Profile.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    new_user_id = await create_supabase_user(payload.email, payload.password, payload.full_name)

    try:
        profile = Profile(
            id=uuid.UUID(new_user_id),
            email=payload.email,
            full_name=payload.full_name,
            role=payload.staff_role,
            shop_id=shop.id,
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    except Exception:
        await db.rollback()
        await delete_supabase_user(new_user_id)
        raise HTTPException(status_code=500, detail="Couldn't finish creating this staff account.")

    return profile


@router.patch("/staff/{staff_id}", response_model=StaffOut)
async def update_staff(
    staff_id: str,
    payload: StaffUpdate,
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Suspend/reactivate, promote/demote between manager<->delivery,
    edit their name, or reset their password — see StaffUpdate for why
    every field is optional. Suspending reuses `Profile.is_suspended`,
    the SAME flag the Admin Panel's "Suspend user" action sets — a
    suspended staff account is locked out on its very next request via
    security.py's get_current_user, identically to a suspended customer
    or shop owner."""
    sid = parse_uuid_or_404(staff_id, "Staff member")
    result = await db.execute(select(Profile).where(Profile.id == sid))
    staff = result.scalar_one_or_none()
    if staff is None or staff.role not in STAFF_ROLES:
        raise HTTPException(status_code=404, detail="Staff member not found")

    shop_result = await db.execute(select(Shop).where(Shop.id == staff.shop_id))
    shop = shop_result.scalar_one_or_none()
    if not _user_owns_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't own this staff member's shop")

    if payload.new_password:
        await update_supabase_user_password(str(staff.id), payload.new_password)

    updates = payload.model_dump(exclude={"new_password"}, exclude_unset=True)
    for key, value in updates.items():
        field = "role" if key == "staff_role" else key
        setattr(staff, field, value)

    await db.commit()
    await db.refresh(staff)
    return staff


@router.delete("/staff/{staff_id}")
async def remove_staff(
    staff_id: str,
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Removes a staff member for good: deletes their Supabase Auth login
    (so they genuinely can't sign in anywhere anymore, not just here)
    and their `profiles` row. Deliberately a hard delete, unlike
    products' soft-delete pattern — a staff account has no order/return
    history of its own referencing it (orders reference the CUSTOMER's
    profile, never the delivery person who marked a status), so there's
    nothing a hard delete would orphan.
    """
    sid = parse_uuid_or_404(staff_id, "Staff member")
    result = await db.execute(select(Profile).where(Profile.id == sid))
    staff = result.scalar_one_or_none()
    if staff is None or staff.role not in STAFF_ROLES:
        raise HTTPException(status_code=404, detail="Staff member not found")

    shop_result = await db.execute(select(Shop).where(Shop.id == staff.shop_id))
    shop = shop_result.scalar_one_or_none()
    if not _user_owns_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't own this staff member's shop")

    await delete_supabase_user(str(staff.id))
    await db.delete(staff)
    await db.commit()

    return {"id": staff_id, "removed": True}
