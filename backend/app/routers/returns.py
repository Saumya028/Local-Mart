import uuid
from datetime import datetime, timezone
from decimal import Decimal

import razorpay
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.return_status import (
    CUSTOMER_CANCELABLE_FROM,
    RETURN_ELIGIBLE_ORDER_STATUSES,
    RETURN_WINDOW,
)
from app.core.security import get_current_user
from app.core.utils import parse_uuid_or_404
from app.models import Order, OrderItem, Product, Profile, ReturnRequest, Shop
from app.schemas.return_request import (
    DifferencePaymentResponse,
    ReturnRequestCreate,
    ReturnRequestOut,
    VerifyDifferencePaymentRequest,
)

router = APIRouter(tags=["returns"])

razorpay_client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))


async def _returned_qty_for_item(db: AsyncSession, order_item_id: uuid.UUID) -> int:
    """
    Quantity of this line item already tied up in a live return/exchange
    request. A rejected or cancelled request frees its quantity back up —
    a customer whose exchange was rejected can still open a plain return
    for the same units, as long as they're still inside the window.
    """
    result = await db.execute(
        select(func.coalesce(func.sum(ReturnRequest.quantity), 0)).where(
            ReturnRequest.order_item_id == order_item_id,
            ReturnRequest.status.notin_(("rejected", "cancelled")),
        )
    )
    return int(result.scalar_one())


def _serialize(rr: ReturnRequest, **extra) -> dict:
    data = ReturnRequestOut.model_validate(rr).model_dump(mode="json")
    data.update(extra)
    return data


@router.post("/orders/{order_id}/returns", response_model=ReturnRequestOut, status_code=201)
async def create_return_request(
    order_id: str,
    payload: ReturnRequestCreate,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Opens a return or exchange request for one line item of a delivered
    order — the customer-facing half of the flow; the shop owner's half
    is PATCH /dashboard/returns/{id}/status in routers/shop_dashboard.py.

    Eligibility, checked in this order (each one is its own clear 400/404
    rather than one generic "not eligible" so the frontend can show the
    customer exactly why):
    1. The order exists and belongs to this user.
    2. The order has actually been delivered (RETURN_ELIGIBLE_ORDER_STATUSES).
    3. It's still within RETURN_WINDOW of the delivered_at timestamp.
    4. The order_item belongs to this order.
    5. The requested quantity doesn't exceed what's left un-claimed on
       that line item (ordered qty minus whatever's already in a live
       return/exchange request for it).
    6. For an exchange: a valid, active replacement product from the SAME
       shop, that isn't just the original product again.
    """
    oid = parse_uuid_or_404(order_id, "Order")
    order_result = await db.execute(select(Order).where(Order.id == oid))
    order = order_result.scalar_one_or_none()
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status not in RETURN_ELIGIBLE_ORDER_STATUSES or order.delivered_at is None:
        raise HTTPException(
            status_code=400, detail="Only delivered orders are eligible for return or exchange"
        )

    deadline = order.delivered_at + RETURN_WINDOW
    if datetime.now(timezone.utc) > deadline:
        raise HTTPException(
            status_code=400,
            detail=f"The {RETURN_WINDOW.days}-day return window for this order has passed",
        )

    item_result = await db.execute(
        select(OrderItem, Product.name, Product.shop_id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(OrderItem.id == payload.order_item_id, OrderItem.order_id == order.id)
    )
    row = item_result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Order item not found")
    item, product_name, shop_id = row

    already_claimed = await _returned_qty_for_item(db, item.id)
    remaining = item.quantity - already_claimed
    if payload.quantity > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Only {remaining} unit(s) of this item can still be returned or exchanged",
        )

    exchange_product = None
    price_difference = Decimal("0")
    if payload.request_type == "exchange":
        if payload.exchange_product_id is None:
            raise HTTPException(
                status_code=400, detail="exchange_product_id is required for an exchange"
            )
        exch_result = await db.execute(select(Product).where(Product.id == payload.exchange_product_id))
        exchange_product = exch_result.scalar_one_or_none()
        if exchange_product is None or not exchange_product.is_active:
            raise HTTPException(status_code=404, detail="Replacement product not found")
        if exchange_product.shop_id != shop_id:
            raise HTTPException(
                status_code=400, detail="You can only exchange for another item from the same shop"
            )
        if exchange_product.id == item.product_id:
            raise HTTPException(status_code=400, detail="Choose a different item to exchange for")
        # Snapshotted now, same reasoning as refund_amount below: what the
        # customer owes (or is owed) on the swap shouldn't drift if the
        # shop changes either product's price before this gets resolved.
        # Positive = replacement costs more, customer owes the gap;
        # negative = it costs less, the shop owes a partial refund;
        # settled the same way plain-return refunds are today (offline,
        # confirmed by the shop marking the request "completed") since
        # there's no gateway path for sending money back out. Only the
        # positive case gets a live payment flow — see
        # POST /returns/{id}/difference-payment below.
        price_difference = (exchange_product.price - item.unit_price) * payload.quantity
    elif payload.exchange_product_id is not None:
        raise HTTPException(status_code=400, detail="exchange_product_id is only used for exchanges")

    rr = ReturnRequest(
        id=uuid.uuid4(),
        order_id=order.id,
        order_item_id=item.id,
        user_id=user.id,
        shop_id=shop_id,
        request_type=payload.request_type,
        quantity=payload.quantity,
        reason=payload.reason,
        comment=payload.comment,
        exchange_product_id=exchange_product.id if exchange_product else None,
        refund_amount=item.unit_price * payload.quantity,
        price_difference=price_difference,
        status="requested",
    )
    db.add(rr)
    await db.commit()
    await db.refresh(rr)

    return _serialize(
        rr,
        product_name=product_name,
        exchange_product_name=exchange_product.name if exchange_product else None,
    )


async def _load_owned_return(db: AsyncSession, return_id: str, user: Profile) -> ReturnRequest:
    rid = parse_uuid_or_404(return_id, "Return request")
    result = await db.execute(select(ReturnRequest).where(ReturnRequest.id == rid))
    rr = result.scalar_one_or_none()
    if rr is None or rr.user_id != user.id:
        raise HTTPException(status_code=404, detail="Return request not found")
    return rr


@router.get("/orders/{order_id}/returns", response_model=list[ReturnRequestOut])
async def list_order_returns(
    order_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Every return/exchange request opened against one specific order —
    shown inline on the order tracking page (app/orders/[id]/page.tsx)."""
    oid = parse_uuid_or_404(order_id, "Order")
    order_result = await db.execute(select(Order).where(Order.id == oid))
    order = order_result.scalar_one_or_none()
    if order is None or order.user_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")

    result = await db.execute(
        select(ReturnRequest, Product.name)
        .join(OrderItem, OrderItem.id == ReturnRequest.order_item_id)
        .join(Product, Product.id == OrderItem.product_id)
        .where(ReturnRequest.order_id == order.id)
        .order_by(ReturnRequest.created_at.desc())
    )
    return [_serialize(rr, product_name=name) for rr, name in result.all()]


@router.get("/returns", response_model=list[ReturnRequestOut])
async def list_my_returns(
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """My Account > My Returns — every return/exchange the customer has
    ever opened, across every order and shop, newest first."""
    result = await db.execute(
        select(ReturnRequest, Product.name, Shop.name)
        .join(OrderItem, OrderItem.id == ReturnRequest.order_item_id)
        .join(Product, Product.id == OrderItem.product_id)
        .join(Shop, Shop.id == ReturnRequest.shop_id)
        .where(ReturnRequest.user_id == user.id)
        .order_by(ReturnRequest.created_at.desc())
    )
    return [_serialize(rr, product_name=pname, shop_name=sname) for rr, pname, sname in result.all()]


@router.post("/returns/{return_id}/difference-payment", response_model=DifferencePaymentResponse)
async def create_difference_payment(
    return_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Opens the top-up payment for an exchange where the replacement item
    costs more than the original — mirrors routers/orders.py's `checkout`
    for a normal cart, just scoped to one small amount instead of a whole
    order. The frontend opens Razorpay's popup against whatever this
    returns, the same widget used at checkout.

    Only reachable once the shop has approved the exchange (paying before
    the shop has even agreed to it would let a customer fund an exchange
    the shop might reject) and only while unpaid. Calling this again
    before paying reuses the same Razorpay Order rather than creating a
    new one each time the customer reopens the payment sheet.
    """
    rr = await _load_owned_return(db, return_id, user)
    if rr.request_type != "exchange" or rr.price_difference <= 0:
        raise HTTPException(status_code=400, detail="This request has no price difference to pay")
    if rr.status != "approved":
        raise HTTPException(
            status_code=400, detail="The shop must approve this exchange before it can be paid"
        )
    if rr.difference_paid:
        raise HTTPException(status_code=400, detail="The price difference has already been paid")

    if rr.difference_razorpay_order_id is None:
        try:
            razorpay_order = razorpay_client.order.create(
                {
                    "amount": int(rr.price_difference * 100),
                    "currency": "INR",
                    "notes": {"return_request_id": str(rr.id), "user_id": str(user.id)},
                }
            )
        except razorpay.errors.BadRequestError as e:
            raise HTTPException(status_code=502, detail=f"Payment provider error: {e}")
        rr.difference_razorpay_order_id = razorpay_order["id"]
        await db.commit()

    return DifferencePaymentResponse(
        razorpay_order_id=rr.difference_razorpay_order_id,
        razorpay_key_id=settings.razorpay_key_id,
        amount=rr.price_difference,
    )


@router.post("/returns/{return_id}/verify-difference-payment", response_model=ReturnRequestOut)
async def verify_difference_payment(
    return_id: str,
    payload: VerifyDifferencePaymentRequest,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Called right after Razorpay's popup reports success for the top-up
    payment — same signature-verification approach as routers/orders.py's
    verify_payment, just flipping `difference_paid` on this one
    ReturnRequest instead of an Order/Payment pair. Once this is true, the
    shop is unblocked from marking the exchange "completed" (see
    routers/shop_dashboard.py's update_return_status).
    """
    rr = await _load_owned_return(db, return_id, user)
    if rr.difference_razorpay_order_id != payload.razorpay_order_id:
        raise HTTPException(status_code=400, detail="This payment doesn't match this return request")

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

    rr.difference_paid = True
    await db.commit()
    await db.refresh(rr)
    return _serialize(rr)


@router.post("/returns/{return_id}/cancel", response_model=ReturnRequestOut)
async def cancel_return_request(
    return_id: str,
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Lets a customer back out of a request they no longer want — only
    while the shop hasn't acted on it yet (see
    app/core/return_status.py's CUSTOMER_CANCELABLE_FROM): once approved,
    the shop is already expecting a pickup, and once rejected there's
    nothing left to cancel.
    """
    rr = await _load_owned_return(db, return_id, user)
    if rr.status not in CUSTOMER_CANCELABLE_FROM:
        raise HTTPException(
            status_code=400, detail=f'Cannot cancel a request that is already "{rr.status}"'
        )
    rr.status = "cancelled"
    rr.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(rr)
    return _serialize(rr)
