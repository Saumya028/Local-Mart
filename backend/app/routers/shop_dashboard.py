import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Literal

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.attribute_validation import validate_attributes
from app.core.cache import invalidate
from app.core.db import get_db
from app.core.order_events import order_changed
from app.core.order_timeline import load_timeline
from app.core.order_status import (
    DELIVERY_PROOF_REQUIRED_STATUSES,
    RECOGNIZED_STATUSES,
    SHOP_CANCELABLE_FROM,
    TERMINAL_STATUSES,
    allowed_transitions_for,
)
from app.core.payment_confirmation import (
    cancel_order_and_release_stock,
    get_payment,
    mark_paid,
    reject_submission,
)
from app.core.return_status import SHOP_ALLOWED_TRANSITIONS
from app.core.return_events import return_changed
from app.core.stock_alerts import effective_threshold, stock_state, sync_shop_stock_alerts, sync_stock_alerts
from app.core.security import require_role
from app.core.supabase_admin import (
    create_supabase_user,
    delete_supabase_user,
    update_supabase_user_password,
)
from app.core.utils import LIKE_ESCAPE_CHAR, escape_like, parse_uuid_or_404
from app.models import Order, OrderItem, Payment, Product, Profile, ReturnRequest, Shop
from app.schemas.dashboard import (
    AnalyticsOut,
    DashboardMetrics,
    DayPoint,
    RecentOrderPreview,
    TopProductOut,
)
from app.schemas.order import DashboardOrderOut, EtaUpdate, OrderStatusUpdate
from app.schemas.notification import OrderEventOut
from app.schemas.product import ProductCreate, ProductDashboardOut, ProductUpdate
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
# apart on what counts as a real sale. Cancelling is a separate action
# (POST /orders/{id}/cancel below, see SHOP_CANCELABLE_FROM), not part of
# either forward table. The only forward path is confirmed ("Pending" in the UI) -> preparing ->
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

    if updates.get("contact_phone", "x") is None:
        raise HTTPException(status_code=400, detail="A contact phone number is required")

    # Checks that need the shop's CURRENT values merged with the request.
    merged_hours = updates["opening_hours"] if "opening_hours" in updates else shop.opening_hours
    merged_slots = updates["slots_enabled"] if "slots_enabled" in updates else shop.slots_enabled
    if merged_slots and not merged_hours:
        raise HTTPException(
            status_code=400,
            detail="Set your opening hours before turning on time slots — slots are generated from them.",
        )
    if updates.get("temporarily_closed") is True:
        until = updates.get("closed_until")
        if until is not None and until <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="“Closed until” must be a time in the future")
    if updates.get("temporarily_closed") is False:
        # Reopening wipes the reason and the end time so they can't resurface next time.
        updates["closed_until"] = None
        updates["closed_message"] = None
    elif "closed_until" in updates and updates["closed_until"] is not None and not (
        updates.get("temporarily_closed", shop.temporarily_closed)
    ):
        raise HTTPException(status_code=400, detail="Turn on “Temporarily closed” to set when you’ll reopen")

    for key, value in updates.items():
        setattr(shop, key, value)
    if "low_stock_threshold" in updates:
        await db.flush()
        await sync_shop_stock_alerts(db, shop.id, notify=False)

    await db.commit()
    await db.refresh(shop)

    await invalidate("shops:list", f"shop:{shop_id}")
    return shop


def _dashboard_product(product: Product, shop_default: int) -> ProductDashboardOut:
    out = ProductDashboardOut.model_validate(product)
    threshold = effective_threshold(product, shop_default)
    out.effective_low_stock_threshold = threshold
    out.stock_status = stock_state(product.stock_qty, threshold) or "ok"
    return out


def _integrity_message(exc: IntegrityError) -> str:
    """Turn a database constraint failure into something an owner can act on."""
    text = str(exc.orig)
    if "ix_products_shop_sku" in text:
        return "Another product in your shop already uses that SKU"
    if "ix_products_shop_barcode" in text:
        return "Another product in your shop already has that barcode"
    if "ck_products_mrp_not_below_price" in text:
        return "MRP can't be lower than the selling price"
    return "That change conflicts with an existing product"


def _check_pricing(price, mrp, unit_value, unit) -> None:
    """Rules that depend on several fields together (checked against the
    product's resulting values, since updates are partial)."""
    if mrp is not None and mrp < price:
        raise HTTPException(
            status_code=400,
            detail="MRP can't be lower than the selling price — raise the MRP or remove it",
        )
    if (unit_value is None) != (unit is None):
        raise HTTPException(status_code=400, detail="Give both the pack size and its unit (e.g. 500 and g), or neither")


@router.post("/products", response_model=ProductDashboardOut)
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
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=_integrity_message(exc)) from exc
    # Opening stock may already be at/below the alert level — record the state
    # quietly (the owner is the one who just typed that number).
    await sync_stock_alerts(db, [product.id], notify=False)
    await db.commit()
    await db.refresh(product)

    await invalidate("categories:list")
    return _dashboard_product(product, shop.low_stock_threshold)


@router.get("/products", response_model=list[ProductDashboardOut])
async def my_products(
    shop_id: uuid.UUID | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100, description="Name, SKU, or an exact barcode"),
    stock: Literal["all", "low", "out"] = Query(default="all", description="Only products at/below their alert level, or sold out"),
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    accessible_shop_ids = await _get_accessible_shop_ids(user, db)

    stmt = select(Product, Shop.low_stock_threshold).join(Shop, Shop.id == Product.shop_id)
    if shop_id is not None:
        stmt = stmt.where(Product.shop_id == shop_id)
    if accessible_shop_ids is not None:
        stmt = stmt.where(Product.shop_id.in_(accessible_shop_ids))
    if q and q.strip():
        pattern = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(
            Product.name.ilike(pattern, escape=LIKE_ESCAPE_CHAR)
            | Product.sku.ilike(pattern, escape=LIKE_ESCAPE_CHAR)
            | (Product.barcode == q.strip())
        )
    level = func.coalesce(Product.low_stock_threshold, Shop.low_stock_threshold)
    if stock == "out":
        stmt = stmt.where(Product.is_active.is_(True), Product.stock_qty <= 0)
    elif stock == "low":
        stmt = stmt.where(Product.is_active.is_(True), Product.stock_qty > 0, Product.stock_qty <= level)
        # Most urgent first.
    order = (Product.stock_qty.asc(), Product.name) if stock != "all" else (Product.created_at.desc(),)

    rows = (await db.execute(stmt.order_by(*order))).all()
    return [_dashboard_product(product, shop_default) for product, shop_default in rows]


@router.get("/products/stock-summary")
async def stock_summary(
    shop_id: uuid.UUID = Query(...),
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """How many ACTIVE products are low or sold out — for the dashboard
    banner and the Inventory tab header."""
    accessible = await _get_accessible_shop_ids(user, db)
    if accessible is not None and shop_id not in accessible:
        raise HTTPException(status_code=403, detail="You don't have access to this shop")
    shop = await db.get(Shop, shop_id)
    if shop is None:
        raise HTTPException(status_code=404, detail="Shop not found")
    level = func.coalesce(Product.low_stock_threshold, shop.low_stock_threshold)
    active = (Product.shop_id == shop_id, Product.is_active.is_(True))
    out = (await db.execute(select(func.count()).select_from(Product).where(*active, Product.stock_qty <= 0))).scalar_one()
    low = (
        await db.execute(
            select(func.count()).select_from(Product).where(*active, Product.stock_qty > 0, Product.stock_qty <= level)
        )
    ).scalar_one()
    return {"low": low, "out": out, "default_threshold": shop.low_stock_threshold}


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


@router.put("/products/{product_id}", response_model=ProductDashboardOut)
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

    _check_pricing(
        updates.get("price", product.price),
        updates["mrp"] if "mrp" in updates else product.mrp,
        updates["unit_value"] if "unit_value" in updates else product.unit_value,
        updates["unit"] if "unit" in updates else product.unit,
    )

    for key, value in updates.items():
        setattr(product, key, value)

    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail=_integrity_message(exc)) from exc
    # Stock, threshold or active status may have crossed the alert line. The
    # owner made this change themselves, so update the state without pinging them.
    await sync_stock_alerts(db, [product.id], notify=False)
    await db.commit()
    await db.refresh(product)
    shop_default = (await db.execute(select(Shop.low_stock_threshold).where(Shop.id == product.shop_id))).scalar_one()

    # The customer-facing product page AND the category counts are both
    # cached — a price/stock/active-status change here must not stay
    # invisible to shoppers for up to a minute just because Redis hasn't
    # naturally expired the old value yet.
    await invalidate(f"product:{product_id}", "categories:list")
    return _dashboard_product(product, shop_default)


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
    await sync_stock_alerts(db, [product.id], notify=False)  # a hidden product raises no alerts
    await db.commit()

    await invalidate(f"product:{product_id}", "categories:list")
    return {"id": product_id, "deactivated": True}


async def _load_order_items(db: AsyncSession, order_ids: list) -> dict:
    """Ordered lines (product name + quantity) for the given orders, keyed
    by order id — what the shop needs to know what to pack."""
    grouped: dict = {}
    if not order_ids:
        return grouped
    rows = await db.execute(
        select(OrderItem, Product)
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.order_id.in_(order_ids))
        .order_by(Product.name)
    )
    for item, product in rows.all():
        # Pack size: the snapshot taken at checkout, else the product's
        # current one (older orders have no snapshot).
        unit_label = item.unit_label or product.unit_label
        # Variant details (size, colour, flavour...) so two variants that
        # share a name can be told apart when packing.
        variant = ", ".join(
            str(v) for v in (product.variant_attributes or {}).values() if v not in (None, "")
        ) or None
        grouped.setdefault(item.order_id, []).append(
            {
                "id": item.id,
                "product_id": item.product_id,
                "product_name": product.name,
                "variant_label": variant,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "unit_label": unit_label,
                "subtotal": item.unit_price * item.quantity,
            }
        )
    return grouped


def _dashboard_order_dict(
    order: Order, buyer_email, buyer_name, item_count, payment: Payment | None, items: list | None = None
) -> dict:
    return {
        "items": items or [],
        "id": order.id,
        "shop_id": order.shop_id,
        "status": order.status,
        "fulfillment_type": order.fulfillment_type,
        "total_amount": order.total_amount,
        "subtotal_amount": order.subtotal_amount,
        "delivery_fee": order.delivery_fee,
        "eta_at": order.eta_at,
        "slot_start": order.slot_start,
        "slot_end": order.slot_end,
        "delivery_address": order.delivery_address,
        "created_at": order.created_at,
        "buyer_email": buyer_email,
        "buyer_name": buyer_name,
        "item_count": int(item_count or 0),
        "delivered_at": order.delivered_at,
        "delivery_proof_photo_url": order.delivery_proof_photo_url,
        "payment_method": payment.method if payment else None,
        "payment_status": payment.status if payment else None,
        "payer_reference": payment.payer_reference if payment else None,
        "payment_marked_at": payment.marked_paid_at if payment else None,
    }


async def _order_response(db: AsyncSession, order: Order) -> dict:
    buyer_result = await db.execute(
        select(Profile.email, Profile.full_name).where(Profile.id == order.user_id)
    )
    buyer_email, buyer_name = buyer_result.one()
    item_count_result = await db.execute(
        select(func.coalesce(func.sum(OrderItem.quantity), 0)).where(OrderItem.order_id == order.id)
    )
    payment = await get_payment(db, order.id)
    items = (await _load_order_items(db, [order.id])).get(order.id, [])
    return _dashboard_order_dict(
        order, buyer_email, buyer_name, item_count_result.scalar_one(), payment, items
    )


async def _load_manageable_order(order_id: str, user: Profile, db: AsyncSession) -> Order:
    oid = parse_uuid_or_404(order_id, "Order")
    order = (await db.execute(select(Order).where(Order.id == oid))).scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    shop = (await db.execute(select(Shop).where(Shop.id == order.shop_id))).scalar_one_or_none()
    if not _user_can_manage_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't have access to this order")
    _require_approved_shop(shop)
    return order


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
        select(Order, Profile.email, Profile.full_name, item_counts.c.item_count, Payment)
        .join(Profile, Profile.id == Order.user_id)
        .outerjoin(item_counts, item_counts.c.order_id == Order.id)
        .outerjoin(Payment, Payment.order_id == Order.id)
    )
    if shop_id is not None:
        stmt = stmt.where(Order.shop_id == shop_id)
    if accessible_shop_ids is not None:
        stmt = stmt.where(Order.shop_id.in_(accessible_shop_ids))

    result = await db.execute(stmt.order_by(Order.created_at.desc()))
    rows = result.all()
    items_by_order = await _load_order_items(db, [r[0].id for r in rows])
    return [
        _dashboard_order_dict(
            order, buyer_email, buyer_name, item_count, payment, items_by_order.get(order.id, [])
        )
        for order, buyer_email, buyer_name, item_count, payment in rows
    ]


@router.patch("/orders/{order_id}/status", response_model=DashboardOrderOut)
async def update_order_status(
    order_id: str,
    payload: OrderStatusUpdate,
    user: Profile = Depends(require_role("shop_owner", "admin", *STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    order = await _load_manageable_order(order_id, user, db)

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

    previous_status = order.status
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
        # Cash is collected at hand-over, so reaching a terminal status IS
        # the moment the shop received it. (A UPI order is only ever
        # marked paid by the shop's explicit confirmation below.)
        payment = await get_payment(db, order.id)
        cash_just_collected = payment is not None and payment.method == "cash" and payment.status != "paid"
        if payment is not None and payment.method == "cash":
            mark_paid(payment)
    else:
        cash_just_collected = False

    await order_changed(
        db, order, "status_changed", actor=user, from_status=previous_status, to_status=payload.status,
        meta={"delivery_proof_photo_url": payload.delivery_proof_photo_url} if payload.delivery_proof_photo_url else None,
    )
    if cash_just_collected:
        await order_changed(
            db, order, "payment_confirmed", actor=user,
            note="Cash collected at hand-over", meta={"auto": "cash_on_handover"},
        )
    await db.commit()

    return await _order_response(db, order)


@router.patch("/orders/{order_id}/eta", response_model=DashboardOrderOut)
async def update_order_eta(
    order_id: str,
    payload: EtaUpdate,
    user: Profile = Depends(require_role("shop_owner", "admin", *STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Tell the customer when to actually expect the order (e.g. "running 20
    minutes late"). Recorded in the order's history and the customer is
    notified."""
    order = await _load_manageable_order(order_id, user, db)
    if order.status == "cancelled" or order.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=400, detail="This order is already finished")
    if (payload.minutes_from_now is None) == (payload.eta_at is None):
        raise HTTPException(status_code=400, detail="Send either minutes_from_now or eta_at")

    now = datetime.now(timezone.utc)
    if payload.minutes_from_now is not None:
        if not 1 <= payload.minutes_from_now <= 24 * 60:
            raise HTTPException(status_code=400, detail="Choose between 1 minute and 24 hours from now")
        new_eta = now + timedelta(minutes=payload.minutes_from_now)
    else:
        if payload.eta_at.tzinfo is None:
            raise HTTPException(status_code=400, detail="eta_at must include a timezone")
        new_eta = payload.eta_at.astimezone(timezone.utc)
        if new_eta <= now or new_eta > now + timedelta(days=7):
            raise HTTPException(status_code=400, detail="The new time must be within the next 7 days")

    old_eta = order.eta_at
    order.eta_at = new_eta
    note = (payload.note or "").strip()[:140] or None
    await order_changed(
        db, order, "eta_changed", actor=user, note=note,
        meta={"from_eta": old_eta.isoformat() if old_eta else None, "to_eta": new_eta.isoformat()},
    )
    await db.commit()
    return await _order_response(db, order)


@router.get("/orders/{order_id}/timeline", response_model=list[OrderEventOut])
async def order_timeline_for_shop(
    order_id: str,
    user: Profile = Depends(require_role("shop_owner", "admin", *STAFF_ROLES)),
    db: AsyncSession = Depends(get_db),
):
    """Full history of an order for the shop team, with WHO (name/email and
    role) did each step — the shop's evidence in a dispute."""
    order = await _load_manageable_order(order_id, user, db)
    return await load_timeline(db, order.id, for_customer=False)


@router.post("/orders/{order_id}/payment/confirm", response_model=DashboardOrderOut)
async def confirm_order_payment(
    order_id: str,
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """The shop confirms the money arrived (UPI transfer seen in their app,
    or cash handed over early). Marks the payment "paid"."""
    order = await _load_manageable_order(order_id, user, db)
    payment = await get_payment(db, order.id)
    if payment is None:
        raise HTTPException(status_code=400, detail="This order has no payment record")
    if order.status == "cancelled":
        raise HTTPException(status_code=400, detail="This order was cancelled")
    was_paid = payment.status == "paid"
    mark_paid(payment)
    if not was_paid:
        await order_changed(db, order, "payment_confirmed", actor=user, meta={"payment_method": payment.method})
    await db.commit()
    return await _order_response(db, order)


@router.post("/orders/{order_id}/payment/reject", response_model=DashboardOrderOut)
async def reject_order_payment(
    order_id: str,
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """The shop did NOT receive the money the customer said they sent —
    puts the payment back to "unpaid" so the customer can retry or switch
    to cash. Can't undo an already-confirmed payment."""
    order = await _load_manageable_order(order_id, user, db)
    payment = await get_payment(db, order.id)
    if payment is None or payment.status != "submitted":
        raise HTTPException(status_code=400, detail="There's no pending payment claim to reject")
    rejected_reference = payment.payer_reference
    reject_submission(payment)
    await order_changed(
        db, order, "payment_rejected", actor=user, meta={"utr": rejected_reference} if rejected_reference else None
    )
    await db.commit()
    return await _order_response(db, order)


@router.post("/orders/{order_id}/cancel", response_model=DashboardOrderOut)
async def cancel_order_as_shop(
    order_id: str,
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """Shop cancels an order before it leaves for delivery / is ready for
    pickup (e.g. out of stock, or the customer never paid). Releases the
    reserved stock. If money was already received the shop must refund it
    themselves, directly — the platform never held it."""
    order = await _load_manageable_order(order_id, user, db)
    if order.status not in SHOP_CANCELABLE_FROM:
        raise HTTPException(status_code=400, detail="This order can no longer be cancelled")
    previous_status = order.status
    await cancel_order_and_release_stock(db, order)
    await order_changed(db, order, "order_cancelled", actor=user, from_status=previous_status, to_status="cancelled")
    await db.commit()
    return await _order_response(db, order)


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


@router.post("/returns/{return_id}/difference/confirm", response_model=ReturnRequestOut)
async def confirm_difference_paid(
    return_id: str,
    user: Profile = Depends(require_role("shop_owner", "admin", "manager")),
    db: AsyncSession = Depends(get_db),
):
    """The shop confirms it received an exchange's price-difference top-up
    (UPI or cash) — unblocks marking the exchange "completed"."""
    rr = (
        await db.execute(
            select(ReturnRequest).where(ReturnRequest.id == parse_uuid_or_404(return_id, "Return request"))
        )
    ).scalar_one_or_none()
    if rr is None:
        raise HTTPException(status_code=404, detail="Return request not found")
    shop = await _get_accessible_shop_or_403(rr.shop_id, user, db)
    _require_approved_shop(shop)
    if rr.request_type != "exchange" or rr.price_difference <= 0:
        raise HTTPException(status_code=400, detail="This request has no price difference to collect")
    if rr.status != "approved":
        raise HTTPException(status_code=400, detail="Approve the exchange first")
    rr.difference_paid = True
    if rr.difference_method is None:
        rr.difference_method = "cash"
    await return_changed(db, rr, "difference_confirmed", actor=user)
    await db.commit()
    await db.refresh(rr)
    return ReturnRequestOut.model_validate(rr).model_dump(mode="json")


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
          already paid that top-up directly to the shop, and the shop
          confirmed receipt (POST /dashboard/returns/{id}/difference/confirm
          sets difference_paid), before this is allowed to complete; a shop owner can't be left holding a costlier item
          with no way to collect the difference.

    The platform never holds money, so no refund is issued here — for the
    REFUND side (or a negative price_difference, a cheaper replacement
    where the shop owes money back) the shop pays the customer back
    directly (UPI, bank transfer, cash); "completed" records that it was
    settled and is the number that should reconcile against it.
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
                    "confirm you've received it before completing"
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
            # settled with the shop by this point.
            original_order_result = await db.execute(select(Order).where(Order.id == rr.order_id))
            original_order = original_order_result.scalar_one_or_none()
            delivery_address = original_order.delivery_address if original_order else ""

            new_order = Order(
                id=uuid.uuid4(),
                user_id=rr.user_id,
                shop_id=rr.shop_id,
                status="confirmed",
                total_amount=exchange_price * rr.quantity,
                subtotal_amount=exchange_price * rr.quantity,
                delivery_address=delivery_address,
            )
            db.add(new_order)
            await db.flush()
            exchange_product = await db.get(Product, rr.exchange_product_id)
            db.add(
                OrderItem(
                    id=uuid.uuid4(),
                    order_id=new_order.id,
                    product_id=rr.exchange_product_id,
                    quantity=rr.quantity,
                    unit_price=exchange_price,
                    mrp=exchange_product.mrp if exchange_product else None,
                    unit_label=exchange_product.unit_label if exchange_product else None,
                )
            )
            rr.new_order_id = new_order.id

    rr.status = payload.status
    if payload.shop_note is not None:
        rr.shop_note = payload.shop_note
    if payload.status in ("rejected", "completed"):
        rr.resolved_at = datetime.now(timezone.utc)

    if payload.status == "completed":
        returned_pid = (
            await db.execute(select(OrderItem.product_id).where(OrderItem.id == rr.order_item_id))
        ).scalar_one_or_none()
        # The returned item went back on the shelf (re-arms its alert); an exchange
        # replacement came off it (may trip one).
        await sync_stock_alerts(db, [p for p in (returned_pid, rr.exchange_product_id) if p is not None], notify=True)

    await return_changed(db, rr, f"return_{payload.status}", actor=user, note=payload.shop_note)
    if new_order is not None:
        await order_changed(
            db, new_order, "order_placed", actor=user, to_status="confirmed",
            note="Replacement order created for an exchange",
            meta={"source": "exchange", "return_id": str(rr.id)},
        )

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
