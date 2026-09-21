import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.attribute_validation import validate_attributes
from app.core.cache import invalidate
from app.core.db import get_db
from app.core.order_status import ALLOWED_TRANSITIONS, RECOGNIZED_STATUSES
from app.core.security import require_role
from app.core.utils import parse_uuid_or_404
from app.models import Order, OrderItem, Product, Profile, Shop
from app.schemas.dashboard import (
    AnalyticsOut,
    DashboardMetrics,
    DayPoint,
    RecentOrderPreview,
    TopProductOut,
)
from app.schemas.order import DashboardOrderOut, OrderStatusUpdate
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.schemas.shop import DashboardShopOut, ShopUpdate

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# See app/core/order_status.py for the transition table and the
# "recognized" (paid) statuses — both are shared with admin.py so
# platform-wide metrics and this dashboard never drift apart on what
# counts as a real sale. Note in particular: ALLOWED_TRANSITIONS has no
# entry leading to "cancelled" anywhere — there is no reject/cancel
# action a shop owner can take here, by design. The only forward path
# is confirmed ("Pending" in the UI) -> preparing -> ready -> delivered.

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
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Requires role="shop_owner"/"admin" — this is a deliberate access gate,
    not just ownership scoping. Becoming a shop_owner is an explicit
    promotion (see scripts/promote_user.py, or the Admin Panel once Phase
    6 ships), never something a plain customer account can trigger
    itself. The frontend checks the user's role BEFORE ever calling this
    endpoint (see the Shop Dashboard page), so a customer never even
    reaches the point of getting a 403 here in normal use — but the
    backend enforces it regardless, since the frontend check alone is
    never the real security boundary.

    Returns DashboardShopOut (not the public ShopOut) — an owner
    genuinely needs to see their own approval_status/docs_status/
    rejection_reason to know what state their application is in.
    """
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
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    shop_result = await db.execute(select(Shop).where(Shop.id == payload.shop_id))
    shop = shop_result.scalar_one_or_none()

    # The `shop_id` in the request body is NEVER trusted by itself — this
    # is the check that stops a shop owner from creating a product under
    # a shop they don't own just by knowing (or guessing) its ID.
    if not _user_owns_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't own this shop")
    _require_approved_shop(shop)
    # Category-specific required fields (e.g. Pharmacy's
    # prescription_required) live in AttributeSchema, defined by an
    # admin — see core/attribute_validation.py.
    await validate_attributes(db, "product", payload.category, payload.attributes)

    product = Product(id=uuid.uuid4(), **payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)

    await invalidate("categories:list")
    return product


@router.get("/products", response_model=list[ProductOut])
async def my_products(
    shop_id: uuid.UUID | None = Query(default=None),
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    owned_shop_ids = None if user.role == "admin" else await _get_owned_shop_ids(user.id, db)

    stmt = select(Product)
    if shop_id is not None:
        stmt = stmt.where(Product.shop_id == shop_id)
    if owned_shop_ids is not None:
        stmt = stmt.where(Product.shop_id.in_(owned_shop_ids))

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
    if not _user_owns_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't own this product")
    _require_approved_shop(shop)

    return product


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    user: Profile = Depends(require_role("shop_owner", "admin")),
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
    user: Profile = Depends(require_role("shop_owner", "admin")),
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
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    owned_shop_ids = None if user.role == "admin" else await _get_owned_shop_ids(user.id, db)

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
    if owned_shop_ids is not None:
        stmt = stmt.where(Order.shop_id.in_(owned_shop_ids))

    result = await db.execute(stmt.order_by(Order.created_at.desc()))
    return [
        {
            "id": order.id,
            "shop_id": order.shop_id,
            "status": order.status,
            "total_amount": order.total_amount,
            "delivery_address": order.delivery_address,
            "created_at": order.created_at,
            "buyer_email": buyer_email,
            "buyer_name": buyer_name,
            "item_count": int(item_count or 0),
        }
        for order, buyer_email, buyer_name, item_count in result.all()
    ]


@router.patch("/orders/{order_id}/status", response_model=DashboardOrderOut)
async def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    oid = parse_uuid_or_404(order_id, "Order")
    result = await db.execute(select(Order).where(Order.id == oid))
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    shop_result = await db.execute(select(Shop).where(Shop.id == order.shop_id))
    shop = shop_result.scalar_one_or_none()
    if not _user_owns_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't own this order")
    _require_approved_shop(shop)

    allowed_next = ALLOWED_TRANSITIONS.get(order.status, set())
    if payload.status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f'Cannot move an order from "{order.status}" to "{payload.status}"',
        )

    order.status = payload.status
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
        "total_amount": order.total_amount,
        "delivery_address": order.delivery_address,
        "created_at": order.created_at,
        "buyer_email": buyer_email,
        "buyer_name": buyer_name,
        "item_count": int(item_count),
    }


@router.get("/summary")
async def sales_summary(
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Paid-orders-only revenue per shop — a "pending" order hasn't actually
    been paid for yet, and a "payment_failed" one never will be, so
    neither should count toward sales. "Paid" here means any status a
    paid order can be in (confirmed/preparing/ready/delivered) — see
    app/core/order_status.py. One GROUP BY query for however many shops
    the user owns, rather than one query per shop.
    """
    owned_shop_ids = None if user.role == "admin" else await _get_owned_shop_ids(user.id, db)

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
    if owned_shop_ids is not None:
        stmt = stmt.where(Shop.id.in_(owned_shop_ids))
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
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Powers the Dashboard home tab: today's headline numbers, the
    7-day revenue chart, top products, and a short recent-orders list —
    all scoped to one shop the requesting user actually owns."""
    shop = await _get_owned_shop_or_403(shop_id, user, db)

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
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """Powers the Analytics tab: all-time totals plus 7-day order-count
    and revenue trend series, scoped to one owned shop."""
    await _get_owned_shop_or_403(shop_id, user, db)

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
