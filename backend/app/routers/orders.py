import uuid
from decimal import Decimal
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cart as cart_store
from app.core.cart import MAX_LINE_QTY
from app.core.db import get_db
from app.core.gst import line_tax
from app.core.idempotency import idempotent
from app.core.invoice import build_invoice_data, next_invoice_number, render_invoice_pdf
from app.core.order_events import order_changed
from app.core.stock_alerts import sync_stock_alerts
from app.core.product_pricing import savings
from app.core.order_timeline import load_timeline
from app.core.order_status import CUSTOMER_CANCELABLE_FROM
from app.core.payment_confirmation import (
    cancel_order_and_release_stock,
    get_payment,
    mark_submitted,
    platform_enabled_methods,
)
from app.core.rate_limit import rate_limit_by_user
from app.core.security import get_current_user
from app.core.shop_hours import describe_eta, zone_of
from app.core.shop_plan import ShopPlan, list_slots, plan_shop_order
from app.core.utils import parse_uuid_or_404
from app.models import (
    Address,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductReview,
    Profile,
    ReturnRequest,
    Shop,
    ShopReview,
)
from app.core.upi import PAYMENT_METHODS, build_upi_link, is_valid_payer_reference
from app.schemas.order import (
    ChangePaymentMethodRequest,
    CheckoutRequest,
    CheckoutResponse,
    MarkPaidRequest,
    OrderDetailOut,
    OrderOut,
    PaymentInfo,
    QuoteRequest,
)
from app.schemas.shop import ShopOut
from app.schemas.notification import OrderEventOut

router = APIRouter(tags=["orders"])


def shop_takes_upi(shop: Shop) -> bool:
    """A shop only really accepts UPI if the owner has it switched on AND
    has given us somewhere to send the money (a UPI id or a QR image)."""
    return bool(shop.accepts_upi and (shop.upi_id or shop.upi_qr_url))


def build_payment_info(order: Order, shop: Shop | None, payment: Payment | None) -> dict | None:
    if payment is None or shop is None:
        return None
    info = PaymentInfo(
        method=payment.method,
        status=payment.status,
        amount=payment.amount,
        payer_reference=payment.payer_reference,
        payee_name=shop.name,
        shop_accepts_upi=shop_takes_upi(shop),
        shop_accepts_cash=bool(shop.accepts_cash),
    )
    if payment.method == "upi":
        info.upi_id = shop.upi_id
        info.upi_qr_url = shop.upi_qr_url
        if shop.upi_id:
            info.upi_link = build_upi_link(
                shop.upi_id, shop.name, Decimal(str(payment.amount)), f"Order {str(order.id)[:8]}"
            )
    return info.model_dump(mode="json")


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
    most expensive one in the app: it does row-locking stock updates.)

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
    6. Create a Payment row per order with the payment method the
       customer chose for that shop ("upi" or "cash"). Payment goes
       DIRECTLY from the customer to the shop — nothing flows through the
       platform, so there is no gateway call here.
    7. Commit everything together, THEN clear the cart.

    Because nothing is committed until step 7, an insufficient-stock
    error on ANY item, a bad address or an invalid payment method rolls
    back the whole attempt — no partial orders, no stock decremented for
    nothing.

    Orders are created as "confirmed" straight away; whether the money
    has actually reached the shop is tracked separately on the Payment
    row (see core/payment_confirmation.py).
    """

    async def do_checkout() -> dict:
        raw_items = await cart_store.get_cart_items(user.id)
        if not raw_items:
            raise HTTPException(status_code=400, detail="Cart is empty")

        # Cart quantities come from Redis, so never trust them: a zero or
        # negative quantity would bypass the stock guard below (and create a
        # negative line total), and an absurd one is never a real order.
        for product_id, qty in raw_items.items():
            if qty < 1 or qty > MAX_LINE_QTY:
                raise HTTPException(
                    status_code=400,
                    detail="Your cart has an invalid quantity. Please review your cart and try again.",
                )

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

        # Cart items are already split by shop into separate Order rows
        # (see the Order model's docstring), so pickup-vs-delivery is
        # decided per shop here too: a customer can pick up from some
        # shops in their cart while having the rest delivered, in one
        # checkout. `pickup_shop_ids` on the request is exactly the set
        # of shop_ids (from THIS cart) the customer chose "Pick up" for —
        # every other shop in items_by_shop gets "delivery".
        pickup_shop_ids = set(payload.pickup_shop_ids)
        shops_result = await db.execute(select(Shop).where(Shop.id.in_(items_by_shop.keys())))
        shops_by_id = {s.id: s for s in shops_result.scalars().all()}
        for shop_id in pickup_shop_ids & items_by_shop.keys():
            shop = shops_by_id[shop_id]
            if not shop.pickup_enabled or not shop.address_line1:
                raise HTTPException(
                    status_code=400, detail=f'"{shop.name}" doesn\'t currently offer pickup'
                )

        # Payment method per shop — direct to the shop, so each shop must
        # actually accept the method chosen for it.
        payment_method_by_shop: dict[uuid.UUID, str] = {}
        platform_methods = await platform_enabled_methods(db)
        for shop_id in items_by_shop:
            shop = shops_by_id[shop_id]
            method = payload.payment_methods.get(shop_id)
            if method in PAYMENT_METHODS and method not in platform_methods:
                raise HTTPException(
                    status_code=400,
                    detail=f"{'UPI' if method == 'upi' else 'Cash'} payments are currently switched off",
                )
            if method not in PAYMENT_METHODS:
                raise HTTPException(
                    status_code=400, detail=f'Choose how to pay "{shop.name}" (UPI or cash)'
                )
            if method == "upi" and not shop_takes_upi(shop):
                raise HTTPException(
                    status_code=400, detail=f'"{shop.name}" doesn\'t currently accept UPI payments'
                )
            if method == "cash" and not shop.accepts_cash:
                raise HTTPException(
                    status_code=400, detail=f'"{shop.name}" doesn\'t currently accept cash'
                )
            payment_method_by_shop[shop_id] = method

        # Is each shop open / is the minimum met / which slot / what fee?
        # One shared function (core/shop_plan.py) so what the checkout page
        # quoted is exactly what is enforced here. Everything is checked
        # BEFORE anything is created, so a refusal leaves no partial orders.
        now = datetime.now(timezone.utc)
        plans: dict[uuid.UUID, ShopPlan] = {}
        for shop_id, items in items_by_shop.items():
            shop_subtotal = sum((p.price * q for p, q in items), Decimal("0"))
            plan = await plan_shop_order(
                db,
                shops_by_id[shop_id],
                shop_subtotal,
                "pickup" if shop_id in pickup_shop_ids else "delivery",
                payload.slots.get(shop_id),
                now=now,
                lock=True,
            )
            if plan.issues:
                raise HTTPException(status_code=plan.issues[0].http_status, detail=plan.issues[0].message)
            plans[shop_id] = plan

        # An address is only needed at all if at least one shop in THIS
        # cart is being delivered — a cart that's 100% pickup never
        # touches the address book.
        needs_delivery_address = bool(items_by_shop.keys() - pickup_shop_ids)
        delivery_address_snapshot: str | None = None
        if needs_delivery_address:
            if payload.address_id is None:
                raise HTTPException(
                    status_code=400, detail="Please add or select a delivery address"
                )
            address_result = await db.execute(select(Address).where(Address.id == payload.address_id))
            address = address_result.scalar_one_or_none()
            if address is None or address.user_id != user.id:
                raise HTTPException(status_code=404, detail="Address not found")
            delivery_address_snapshot = address.snapshot()

        created_orders: list[Order] = []
        reserved_product_ids: list[uuid.UUID] = []
        grand_total = Decimal("0")

        for shop_id, items in items_by_shop.items():
            is_pickup = shop_id in pickup_shop_ids
            order = Order(
                id=uuid.uuid4(),
                user_id=user.id,
                shop_id=shop_id,
                status="confirmed",
                total_amount=Decimal("0"),  # filled in below once we know the line totals
                fulfillment_type="pickup" if is_pickup else "delivery",
                delivery_address=None if is_pickup else delivery_address_snapshot,
                eta_at=plans[shop_id].eta_at,
                slot_start=plans[shop_id].slot[0] if plans[shop_id].slot else None,
                slot_end=plans[shop_id].slot[1] if plans[shop_id].slot else None,
            )
            db.add(order)
            await db.flush()  # so order.id is usable as a foreign key on the OrderItems below

            order_total = Decimal("0")
            order_tax = Decimal("0.00")
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
                order_tax += line_tax(product.price, qty, product.gst_rate)
                reserved_product_ids.append(product.id)
                db.add(
                    OrderItem(
                        id=uuid.uuid4(),
                        order_id=order.id,
                        product_id=product.id,
                        quantity=qty,
                        unit_price=product.price,
                        # What the customer saw: so a later edit to the product
                        # can't change the savings/pack size shown on this order.
                        mrp=product.mrp,
                        unit_label=product.unit_label,
                        gst_rate=product.gst_rate or 0,
                        hsn_code=product.hsn_code,
                    )
                )

            # The fee is decided once, now, and stored on the order — a later
            # change to the shop's pricing can never alter this order.
            order.subtotal_amount = order_total
            order.tax_amount = order_tax
            order.delivery_fee = plans[shop_id].delivery_fee
            order.total_amount = order_total + order_tax + plans[shop_id].delivery_fee
            order.invoice_number = await next_invoice_number(db, shops_by_id[shop_id], now)
            # Business buyers: snapshot their GSTIN so the invoice is a proper B2B one.
            if user.gstin:
                order.buyer_gstin = user.gstin
                order.buyer_business_name = user.business_name
            grand_total += order.total_amount
            created_orders.append(order)

        for order in created_orders:
            db.add(
                Payment(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    status="unpaid",
                    amount=order.total_amount,
                    method=payment_method_by_shop[order.shop_id],
                )
            )

        # Tell the shop if this sale just pushed something under its low-stock
        # line (best effort: never blocks the order).
        await sync_stock_alerts(db, reserved_product_ids, notify=True)
        await db.flush()  # payments must be visible to the notification templates
        for order in created_orders:
            await order_changed(
                db, order, "order_placed", actor=user, actor_role="customer", to_status="confirmed",
                meta={
                    "payment_method": payment_method_by_shop[order.shop_id],
                    "fulfillment_type": order.fulfillment_type,
                },
            )

        await db.commit()
        await cart_store.clear_cart(user.id)

        return {
            "orders": [OrderOut.model_validate(o).model_dump(mode="json") for o in created_orders],
            "total_amount": str(grand_total),
        }

    idempotency_redis_key = f"idempotency:checkout:{user.id}:{idempotency_key}"
    return await idempotent(idempotency_redis_key, ttl_seconds=86400, action=do_checkout)


@router.post("/orders/quote")
async def quote_order(
    payload: QuoteRequest,
    user: Profile = Depends(rate_limit_by_user("quote", limit=120, window_seconds=60)),
    db: AsyncSession = Depends(get_db),
):
    """
    "What would checkout look like right now?" — per shop in the cart: the
    delivery fee, free-delivery progress, minimum order, whether the shop is
    open, the ETA, the bookable time slots (with seats left) and every
    reason checkout would currently refuse (`issues`). Nothing is created or
    reserved. Uses the same code as the real checkout (core/shop_plan.py).
    """
    raw_items = await cart_store.get_cart_items(user.id)
    products = {}
    if raw_items:
        result = await db.execute(select(Product).where(Product.id.in_([uuid.UUID(pid) for pid in raw_items])))
        products = {str(p.id): p for p in result.scalars().all()}

    groups: dict[uuid.UUID, list[tuple[Product, int]]] = {}
    for pid, qty in raw_items.items():
        product = products.get(pid)
        if product is not None and product.is_active and 1 <= qty <= MAX_LINE_QTY:
            groups.setdefault(product.shop_id, []).append((product, qty))
    shops = {}
    if groups:
        shop_rows = await db.execute(select(Shop).where(Shop.id.in_(groups.keys())))
        shops = {s.id: s for s in shop_rows.scalars().all()}

    now = datetime.now(timezone.utc)
    pickup = set(payload.pickup_shop_ids)
    out = []
    grand_total = Decimal("0")
    can_checkout = bool(groups)
    for shop_id, items in groups.items():
        shop = shops[shop_id]
        fulfillment = "pickup" if shop_id in pickup and shop.pickup_enabled and shop.address_line1 else "delivery"
        subtotal = sum((p.price * q for p, q in items), Decimal("0"))
        tax = sum((line_tax(p.price, q, p.gst_rate) for p, q in items), Decimal("0.00"))
        plan = await plan_shop_order(db, shop, subtotal, fulfillment, payload.slots.get(shop_id), now=now)
        plan.total += tax
        grand_total += plan.total
        can_checkout = can_checkout and not plan.issues
        slot = plan.slot
        out.append(
            {
                "shop_id": str(shop.id),
                "shop_name": shop.name,
                "timezone": shop.timezone,
                "fulfillment": fulfillment,
                "subtotal": str(plan.subtotal),
                "delivery_fee": str(plan.delivery_fee),
                "tax": str(tax),
                "total": str(plan.total),
                "min_order_amount": str(plan.min_order_amount),
                "min_order_shortfall": str(plan.min_order_shortfall),
                "free_delivery_above": str(plan.free_delivery_above) if plan.free_delivery_above is not None else None,
                "free_delivery_remaining": str(plan.free_delivery_remaining) if plan.free_delivery_remaining is not None else None,
                "open": plan.status.as_dict(),
                "eta_at": plan.eta_at.isoformat() if plan.eta_at else None,
                "eta_text": describe_eta(plan.eta_at, slot[0] if slot else None, slot[1] if slot else None, zone_of(shop), now),
                "slots_enabled": shop.slots_enabled,
                "slots": await list_slots(db, shop, fulfillment, now) if shop.slots_enabled else [],
                "issues": [{"code": i.code, "message": i.message} for i in plan.issues],
            }
        )
    return {"shops": out, "grand_total": str(grand_total), "can_checkout": can_checkout}


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
        select(Order, Shop.name, func.coalesce(item_counts.c.item_count, 0), Payment.method, Payment.status)
        .join(Shop, Shop.id == Order.shop_id)
        .outerjoin(item_counts, item_counts.c.order_id == Order.id)
        .outerjoin(Payment, Payment.order_id == Order.id)
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )
    result = await db.execute(stmt)
    return [
        {
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
            "shop_name": shop_name,
            "item_count": item_count,
            "delivered_at": order.delivered_at,
            "delivery_proof_photo_url": order.delivery_proof_photo_url,
            "payment_method": pay_method,
            "payment_status": pay_status,
        }
        for order, shop_name, item_count, pay_method, pay_status in result.all()
    ]


async def _load_owned_order(db: AsyncSession, order_id: str, user: Profile) -> Order:
    """Shared by get_order and the payment/cancel endpoints below — scoped to the
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
    order_items = items_result.all()

    # One grouped query for every item's already-claimed return quantity,
    # rather than a query per line item — see routers/returns.py's
    # _returned_qty_for_item for the same "non-cancelled/non-rejected"
    # rule applied per-item there.
    returned_result = await db.execute(
        select(ReturnRequest.order_item_id, func.coalesce(func.sum(ReturnRequest.quantity), 0))
        .where(
            ReturnRequest.order_id == order.id,
            ReturnRequest.status.notin_(("rejected", "cancelled")),
        )
        .group_by(ReturnRequest.order_item_id)
    )
    returned_by_item = dict(returned_result.all())

    # The customer's own reviews of these products / this shop, so the
    # order page can offer "Rate" vs "Edit your review" without extra calls.
    review_result = await db.execute(
        select(ProductReview.product_id, ProductReview.id).where(
            ProductReview.user_id == order.user_id,
            ProductReview.product_id.in_([item.product_id for item, _ in order_items]),
        )
    )
    review_by_product = dict(review_result.all())
    shop_review_id = (
        await db.execute(
            select(ShopReview.id).where(ShopReview.user_id == order.user_id, ShopReview.shop_id == order.shop_id)
        )
    ).scalar_one_or_none()

    items = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "product_name": name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "subtotal": item.unit_price * item.quantity,
            "mrp": item.mrp,
            "unit_label": item.unit_label,
            "gst_rate": item.gst_rate,
            "returned_qty": int(returned_by_item.get(item.id, 0)),
            "review_id": review_by_product.get(item.product_id),
        }
        for item, name in order_items
    ]

    data = OrderOut.model_validate(order).model_dump(mode="json")
    data["shop"] = ShopOut.model_validate(shop).model_dump(mode="json") if shop else None
    data["shop_name"] = shop.name if shop else None
    data["item_count"] = sum(i["quantity"] for i in items)
    data["items"] = items
    data["savings_amount"] = sum(
        (savings(i["mrp"], i["unit_price"]) * i["quantity"] for i in items), Decimal("0.00")
    )
    data["shop_review_id"] = shop_review_id
    payment = await get_payment(db, order.id)
    data["payment_method"] = payment.method if payment else None
    data["payment_status"] = payment.status if payment else None
    data["payment"] = build_payment_info(order, shop, payment)
    return data


@router.get("/orders/{order_id}", response_model=OrderDetailOut)
async def get_order(
    order_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Full order detail for the tracking page: status, shop, every line
    item, and — for the owner only — how to pay the shop directly."""
    order = await _load_owned_order(db, order_id, user)
    return await _build_order_detail(db, order)


@router.get("/orders/{order_id}/invoice")
async def order_invoice(
    order_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The customer's GST invoice for their own order, as a PDF."""
    order = await _load_owned_order(db, order_id, user)
    inv = await build_invoice_data(db, order)
    return Response(
        render_invoice_pdf(inv),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="invoice-{inv.number.replace("/", "-")}.pdf"'},
    )


@router.get("/orders/{order_id}/timeline", response_model=list[OrderEventOut])
async def order_timeline(
    order_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Everything that has happened to this order, oldest first — the
    customer's own record (who did what, when, including delivery proof).
    Staff names/emails are never shown here, only "The shop"."""
    order = await _load_owned_order(db, order_id, user)
    return await load_timeline(db, order.id, for_customer=True)


@router.post("/orders/{order_id}/payment/mark-paid", response_model=OrderDetailOut)
async def mark_order_paid(
    order_id: str,
    payload: MarkPaidRequest,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Customer taps "I've paid" after sending money by UPI. This does NOT
    mark the order paid — the platform can't see the transfer. It moves
    the payment to "submitted" so the shop sees a "Confirm payment
    received" prompt (with the UTR, if given) in their dashboard.
    """
    order = await _load_owned_order(db, order_id, user)
    payment = await get_payment(db, order.id)
    if order.status == "cancelled":
        raise HTTPException(status_code=400, detail="This order was cancelled")
    if payment is None or payment.method != "upi":
        raise HTTPException(status_code=400, detail="This order isn't set to pay by UPI")
    if payment.status == "paid":
        return await _build_order_detail(db, order)

    ref = (payload.payer_reference or "").strip()
    if ref and not is_valid_payer_reference(ref):
        raise HTTPException(
            status_code=400,
            detail="The transaction/UTR number should be 8-30 letters or digits",
        )
    before = (payment.status, payment.payer_reference)
    mark_submitted(payment, ref or None)
    if (payment.status, payment.payer_reference) != before:
        await order_changed(
            db, order, "payment_submitted", actor=user, actor_role="customer", meta={"utr": ref} if ref else None
        )
    await db.commit()
    return await _build_order_detail(db, order)


@router.post("/orders/{order_id}/payment/change-method", response_model=OrderDetailOut)
async def change_payment_method(
    order_id: str,
    payload: ChangePaymentMethodRequest,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Switch between UPI and cash while the order isn't paid yet (e.g.
    the shop said it never received the UPI transfer)."""
    order = await _load_owned_order(db, order_id, user)
    payment = await get_payment(db, order.id)
    if order.status == "cancelled" or payment is None:
        raise HTTPException(status_code=400, detail="This order can't be changed")
    if payment.status == "paid":
        raise HTTPException(status_code=400, detail="This order is already paid")
    if payload.method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="Choose UPI or cash")

    shop_result = await db.execute(select(Shop).where(Shop.id == order.shop_id))
    shop = shop_result.scalar_one()
    if payload.method not in await platform_enabled_methods(db):
        raise HTTPException(status_code=400, detail="That payment method is currently switched off")
    if payload.method == "upi" and not shop_takes_upi(shop):
        raise HTTPException(status_code=400, detail="This shop doesn't currently accept UPI")
    if payload.method == "cash" and not shop.accepts_cash:
        raise HTTPException(status_code=400, detail="This shop doesn't currently accept cash")

    old_method = payment.method
    payment.method = payload.method
    payment.status = "unpaid"
    payment.payer_reference = None
    payment.marked_paid_at = None
    await order_changed(
        db, order, "payment_method_changed", actor=user, actor_role="customer",
        meta={"from_method": old_method, "to_method": payload.method},
    )
    await db.commit()
    return await _build_order_detail(db, order)


@router.post("/orders/{order_id}/cancel", response_model=OrderDetailOut)
async def cancel_order(
    order_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Customer cancels an order — only before the shop starts preparing it
    and only while nothing has been paid or marked as paid (otherwise the
    shop may already be holding the customer's money; they'd have to
    contact the shop). Releases the reserved stock.
    """
    order = await _load_owned_order(db, order_id, user)
    payment = await get_payment(db, order.id)
    if order.status not in CUSTOMER_CANCELABLE_FROM:
        raise HTTPException(
            status_code=400,
            detail="The shop has already started on this order — please contact the shop to cancel",
        )
    if payment is not None and payment.status in ("submitted", "paid"):
        raise HTTPException(
            status_code=400,
            detail="This order has a payment on record — please contact the shop to cancel",
        )
    previous_status = order.status
    await cancel_order_and_release_stock(db, order)
    await order_changed(
        db, order, "order_cancelled", actor=user, actor_role="customer",
        from_status=previous_status, to_status="cancelled",
    )
    await db.commit()
    return await _build_order_detail(db, order)
