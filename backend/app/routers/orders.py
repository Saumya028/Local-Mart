import uuid
from decimal import Decimal

import razorpay
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cart as cart_store
from app.core.config import settings
from app.core.db import get_db
from app.core.idempotency import idempotent
from app.core.payment_confirmation import mark_payment_captured, mark_payment_failed
from app.core.rate_limit import rate_limit_by_user
from app.core.security import get_current_user
from app.core.utils import parse_uuid_or_404
from app.models import Address, Order, OrderItem, Payment, Product, Profile, Shop
from app.schemas.order import (
    CheckoutRequest,
    CheckoutResponse,
    OrderDetailOut,
    OrderOut,
    VerifyPaymentRequest,
)
from app.schemas.shop import ShopOut

router = APIRouter(tags=["orders"])

razorpay_client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


@router.post("/orders", response_model=CheckoutResponse)
async def checkout(
    payload: CheckoutRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user: Profile = Depends(rate_limit_by_user("checkout", limit=10, window_seconds=60)),
    db: AsyncSession = Depends(get_db),
):
    """
    The whole checkout flow:

    (Rate-limited to 10 attempts/minute per user — see core/rate_limit.py.
    That's generous for a real shopper, who checks out at most a handful
    of times a session, but stops a runaway frontend retry loop or a
    scripted abuser from hammering this endpoint, which is by far the
    most expensive one in the app: it does row-locking stock updates AND
    calls the Razorpay API on every single attempt.)

    1. Resolve the chosen address (Phase 4: a saved address, not free
       text) and snapshot it into a formatted string — orders should
       still show the correct address even if the address book entry is
       later edited or deleted.
    2. Read the cart from Redis. Prices and stock are NEVER trusted from
       anywhere but Postgres, checked fresh right here.
    3. Group cart lines by shop — a cart spanning 3 shops becomes 3 Order
       rows (see the Order model's docstring for why).
    4. For each item, atomically reserve stock with a single
       UPDATE ... WHERE stock_qty >= qty ... RETURNING statement — this is
       race-safe (verified in Phase 3 under a simulated concurrent-buyer
       race): two checkouts for the same last unit cannot both succeed.
    5. Create Order + OrderItem rows. Nothing is committed yet.
    6. Create ONE Razorpay Order for the whole cart total, and a Payment
       row per order pointing at it.
    7. Commit everything together, THEN clear the cart.

    Because nothing is committed until step 7, an insufficient-stock
    error on ANY item, a bad address, or the Razorpay API call itself
    failing all roll back the whole attempt — no partial orders, no stock
    decremented for nothing.

    This endpoint only ever creates a "pending" order — actual payment
    confirmation happens via the Razorpay webhook and/or POST
    /orders/verify-payment (see that endpoint and
    core/payment_confirmation.py for why there are two paths).
    """

    async def do_checkout() -> dict:
        address_result = await db.execute(select(Address).where(Address.id == payload.address_id))
        address = address_result.scalar_one_or_none()
        if address is None or address.user_id != user.id:
            raise HTTPException(status_code=404, detail="Address not found")
        delivery_address_snapshot = f"{address.label}: {address.line1}, {address.city}"

        raw_items = await cart_store.get_cart_items(user.id)
        if not raw_items:
            raise HTTPException(status_code=400, detail="Cart is empty")

        product_ids = [uuid.UUID(pid) for pid in raw_items.keys()]
        result = await db.execute(select(Product).where(Product.id.in_(product_ids)))
        products_by_id = {str(p.id): p for p in result.scalars().all()}

        items_by_shop: dict[uuid.UUID, list[tuple[Product, int]]] = {}
        for product_id, qty in raw_items.items():
            product = products_by_id.get(product_id)
            if product is None or not product.is_active:
                raise HTTPException(
                    status_code=400, detail=f"Product {product_id} is no longer available"
                )
            items_by_shop.setdefault(product.shop_id, []).append((product, qty))

        created_orders: list[Order] = []
        grand_total = Decimal("0")

        for shop_id, items in items_by_shop.items():
            order = Order(
                id=uuid.uuid4(),
                user_id=user.id,
                shop_id=shop_id,
                status="pending",
                total_amount=Decimal("0"),  # filled in below once we know the line totals
                delivery_address=delivery_address_snapshot,
            )
            db.add(order)
            await db.flush()  # so order.id is usable as a foreign key on the OrderItems below

            order_total = Decimal("0")
            for product, qty in items:
                stmt = (
                    update(Product)
                    .where(Product.id == product.id, Product.stock_qty >= qty)
                    .values(stock_qty=Product.stock_qty - qty)
                    .returning(Product.id)
                )
                reserved = await db.execute(stmt)
                if reserved.first() is None:
                    raise HTTPException(
                        status_code=409, detail=f'Not enough stock for "{product.name}"'
                    )

                line_total = product.price * qty
                order_total += line_total
                db.add(
                    OrderItem(
                        id=uuid.uuid4(),
                        order_id=order.id,
                        product_id=product.id,
                        quantity=qty,
                        unit_price=product.price,
                    )
                )

            order.total_amount = order_total
            grand_total += order_total
            created_orders.append(order)

        # Razorpay amounts are integers in the smallest currency unit
        # (paise for INR) — hence the *100. This call creates the Order
        # on Razorpay's side (not to be confused with our own Order rows
        # above) that the frontend's Checkout widget opens a payment
        # popup against.
        try:
            razorpay_order = razorpay_client.order.create(
                {
                    "amount": int(grand_total * 100),
                    "currency": "INR",
                    "notes": {
                        "user_id": str(user.id),
                        "order_ids": ",".join(str(o.id) for o in created_orders),
                    },
                }
            )
        except razorpay.errors.BadRequestError as e:
            raise HTTPException(status_code=502, detail=f"Payment provider error: {e}")

        for order in created_orders:
            db.add(
                Payment(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    provider_ref=razorpay_order["id"],
                    status="pending",
                    amount=order.total_amount,
                    method="card",
                )
            )

        await db.commit()
        await cart_store.clear_cart(user.id)

        return {
            "orders": [OrderOut.model_validate(o).model_dump(mode="json") for o in created_orders],
            "razorpay_order_id": razorpay_order["id"],
            "razorpay_key_id": settings.razorpay_key_id,
            "total_amount": str(grand_total),
        }

    idempotency_redis_key = f"idempotency:checkout:{user.id}:{idempotency_key}"
    return await idempotent(idempotency_redis_key, ttl_seconds=86400, action=do_checkout)


@router.post("/orders/verify-payment")
async def verify_payment(
    payload: VerifyPaymentRequest,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Called right after Razorpay's Checkout popup reports success (see
    checkout/page.tsx's `handler`) — a reliable alternative to waiting on
    the webhook alone. See core/payment_confirmation.py's module
    docstring for the full reasoning; short version: the webhook has to
    be registered against wherever this backend is currently reachable,
    and if that's ever missed, stale, or blocked, a real successful
    payment sits at "Awaiting payment" forever with nothing to ever flip
    it. This path doesn't trust the browser's word that payment
    succeeded — it re-derives the same HMAC signature Razorpay's own
    docs recommend verifying, using our key secret, which only Razorpay
    could have produced correctly in the first place.
    """
    try:
        razorpay_client.utility.verify_payment_signature(
            {
                "razorpay_order_id": payload.razorpay_order_id,
                "razorpay_payment_id": payload.razorpay_payment_id,
                "razorpay_signature": payload.razorpay_signature,
            }
        )
    except razorpay.errors.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Payment signature could not be verified")

    # A valid signature proves the payment is real, not that THIS user
    # is the one who made it — confirm the caller actually owns (at
    # least one of) the order(s) this Razorpay Order paid for before
    # touching anything, the same way get_order below scopes lookups to
    # `Order.user_id == user.id`.
    owns_order = await db.execute(
        select(Payment.id)
        .join(Order, Order.id == Payment.order_id)
        .where(Payment.provider_ref == payload.razorpay_order_id, Order.user_id == user.id)
        .limit(1)
    )
    if owns_order.first() is None:
        raise HTTPException(status_code=404, detail="Order not found")

    # Safe to call even if the webhook already landed first (or lands a
    # moment later) — see mark_payment_captured's docstring on why
    # marking an already-"succeeded" payment succeeded again is a no-op.
    await mark_payment_captured(db, payload.razorpay_order_id)
    await db.commit()

    return {"status": "confirmed"}


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Order history for My Account > My Orders. Joins in the shop's name
    and a total item quantity so each card can be rendered from this one
    call — deliberately still no line items (see OrderDetailOut for
    those), just enough for a list.
    """
    item_counts = (
        select(OrderItem.order_id, func.coalesce(func.sum(OrderItem.quantity), 0).label("item_count"))
        .group_by(OrderItem.order_id)
        .subquery()
    )
    stmt = (
        select(Order, Shop.name, func.coalesce(item_counts.c.item_count, 0))
        .join(Shop, Shop.id == Order.shop_id)
        .outerjoin(item_counts, item_counts.c.order_id == Order.id)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )
    result = await db.execute(stmt)
    return [
        {
            "id": order.id,
            "shop_id": order.shop_id,
            "status": order.status,
            "total_amount": order.total_amount,
            "delivery_address": order.delivery_address,
            "created_at": order.created_at,
            "shop_name": shop_name,
            "item_count": item_count,
        }
        for order, shop_name, item_count in result.all()
    ]


async def _load_owned_order(db: AsyncSession, order_id: str, user: Profile) -> Order:
    """Shared by get_order and sync_payment_status below — scoped to the
    requesting user so a shop owner or another customer can never look up
    someone else's order by guessing IDs."""
    oid = parse_uuid_or_404(order_id, "Order")
    result = await db.execute(select(Order).where(Order.id == oid))
    order = result.scalar_one_or_none()
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


async def _build_order_detail(db: AsyncSession, order: Order) -> dict:
    shop_result = await db.execute(select(Shop).where(Shop.id == order.shop_id))
    shop = shop_result.scalar_one_or_none()

    items_result = await db.execute(
        select(OrderItem, Product.name)
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.order_id == order.id)
    )
    items = [
        {
            "product_id": item.product_id,
            "product_name": name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "subtotal": item.unit_price * item.quantity,
        }
        for item, name in items_result.all()
    ]

    data = OrderOut.model_validate(order).model_dump(mode="json")
    data["shop"] = ShopOut.model_validate(shop).model_dump(mode="json") if shop else None
    data["shop_name"] = shop.name if shop else None
    data["item_count"] = sum(i["quantity"] for i in items)
    data["items"] = items
    return data


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
async def get_order(
    order_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Full order detail for the tracking page: status, shop, and every line
    item. The Checkout page also polls this right after payment — see
    sync_payment_status below for how a "pending" order actually gets a
    chance to become "confirmed" between polls, since this endpoint by
    itself only reads whatever's already in Postgres.
    """
    order = await _load_owned_order(db, order_id, user)
    return await _build_order_detail(db, order)


@router.post("/orders/{order_id}/sync-payment-status", response_model=OrderDetailOut)
async def sync_payment_status(
    order_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Asks Razorpay directly, right now, what actually happened to this
    order's payment — a third, on-demand path alongside the webhook and
    POST /orders/verify-payment (see core/payment_confirmation.py's
    docstring), and the one that can fix an order that's ALREADY stuck:
    the other two only ever fire once, at the moment a payment succeeds,
    so an order that missed both (say, the webhook was never registered
    for wherever this backend happened to be reachable at the time, AND
    the browser tab was closed before the verify-payment call went out)
    has nothing left to un-stick it — nothing else asks Razorpay again
    later. This does, using Razorpay's `GET /orders/{id}/payments` API
    with our own server-side key (no signature from the browser needed,
    since we're asking Razorpay directly rather than trusting anything
    the client hands us).

    The order tracking page calls this on every poll while status is
    still "pending" (see app/orders/[id]/page.tsx) — so simply opening
    that page again is what reconciles an order that got stuck before
    this endpoint existed, not just new ones going forward.
    """
    order = await _load_owned_order(db, order_id, user)

    if order.status != "pending":
        # Nothing to reconcile — either already resolved, or in some
        # other terminal-ish state (e.g. shipped) this shouldn't touch.
        return await _build_order_detail(db, order)

    payment_result = await db.execute(select(Payment).where(Payment.order_id == order.id))
    payment = payment_result.scalar_one_or_none()
    if payment is None:
        return await _build_order_detail(db, order)

    try:
        remote = razorpay_client.order.payments(payment.provider_ref)
    except razorpay.errors.BadRequestError:
        # Razorpay itself doesn't recognize this order_id (shouldn't
        # normally happen) — nothing to reconcile against, so just
        # report the order as it stands rather than failing the whole
        # page load over it.
        return await _build_order_detail(db, order)

    remote_payments = remote.get("items", [])
    captured = next((p for p in remote_payments if p.get("status") == "captured"), None)
    failed = next((p for p in remote_payments if p.get("status") == "failed"), None)

    if captured is not None:
        await mark_payment_captured(db, payment.provider_ref, method=captured.get("method"))
        await db.commit()
        await db.refresh(order)
    elif failed is not None and not any(p.get("status") == "captured" for p in remote_payments):
        await mark_payment_failed(db, payment.provider_ref)
        await db.commit()
        await db.refresh(order)
    # Else: still genuinely pending on Razorpay's side too (e.g. the
    # shopper hasn't finished the popup yet) — leave it as is.

    return await _build_order_detail(db, order)
