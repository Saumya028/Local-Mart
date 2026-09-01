import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate
from app.core.db import get_db
from app.core.security import require_role
from app.core.utils import parse_uuid_or_404
from app.models import Order, Product, Profile, Shop
from app.schemas.order import DashboardOrderOut, OrderStatusUpdate
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.schemas.shop import ShopOut, ShopUpdate

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Forward-only status transitions a shop owner is allowed to make.
# "pending" -> "confirmed"/"payment_failed" is deliberately absent here —
# only Razorpay's webhook (routers/webhooks.py) gets to make that call,
# since only Razorpay actually knows whether the payment succeeded.
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "confirmed": {"shipped", "cancelled"},
    "shipped": {"delivered"},
}


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


@router.get("/shops", response_model=list[ShopOut])
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
    """
    result = await db.execute(select(Shop).where(Shop.owner_id == user.id))
    return result.scalars().all()


@router.put("/shops/{shop_id}", response_model=ShopOut)
async def update_my_shop(
    shop_id: str,
    payload: ShopUpdate,
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    sid = parse_uuid_or_404(shop_id, "Shop")
    result = await db.execute(select(Shop).where(Shop.id == sid))
    shop = result.scalar_one_or_none()

    if not _user_owns_shop(shop, user):
        raise HTTPException(status_code=403, detail="You don't own this shop")

    for key, value in payload.model_dump(exclude_unset=True).items():
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

    return product


@router.put("/products/{product_id}", response_model=ProductOut)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    product = await _get_owned_product_or_403(product_id, user, db)

    for key, value in payload.model_dump(exclude_unset=True).items():
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

    stmt = select(Order, Profile.email).join(Profile, Profile.id == Order.user_id)
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
        }
        for order, buyer_email in result.all()
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

    allowed_next = ALLOWED_TRANSITIONS.get(order.status, set())
    if payload.status not in allowed_next:
        raise HTTPException(
            status_code=400,
            detail=f'Cannot move an order from "{order.status}" to "{payload.status}"',
        )

    order.status = payload.status
    await db.commit()

    buyer_result = await db.execute(select(Profile.email).where(Profile.id == order.user_id))
    buyer_email = buyer_result.scalar_one()

    return {
        "id": order.id,
        "shop_id": order.shop_id,
        "status": order.status,
        "total_amount": order.total_amount,
        "delivery_address": order.delivery_address,
        "created_at": order.created_at,
        "buyer_email": buyer_email,
    }


@router.get("/summary")
async def sales_summary(
    user: Profile = Depends(require_role("shop_owner", "admin")),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirmed-orders-only revenue per shop — a "pending" order hasn't
    actually been paid for yet, and a "payment_failed" one never will be,
    so neither should count toward sales. One GROUP BY query for however
    many shops the user owns, rather than one query per shop.
    """
    owned_shop_ids = None if user.role == "admin" else await _get_owned_shop_ids(user.id, db)

    stmt = (
        select(
            Shop.id,
            Shop.name,
            func.count(Order.id).filter(Order.status == "confirmed"),
            func.coalesce(func.sum(Order.total_amount).filter(Order.status == "confirmed"), 0),
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
