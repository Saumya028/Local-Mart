import json
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate
from app.core.config import settings
from app.core.db import AsyncSessionLocal, get_db
from app.core.security import require_role
from app.core.sponsorship import (
    activate_purchase,
    create_razorpay_order,
    payment_mode,
    verify_checkout_signature,
    verify_webhook_signature,
)
from app.core.utils import parse_uuid_or_404
from app.models import Profile, SponsorshipPlan, SponsorshipPurchase
from app.routers.shop_dashboard import _get_owned_shop_or_403
from app.schemas.sponsorship import (
    CheckoutRequest,
    CheckoutResponse,
    ConfirmRequest,
    PlanOut,
    PlansResponse,
    PurchaseOut,
    SponsorshipStatus,
)

router = APIRouter(prefix="/sponsorship", tags=["sponsorship"])

# Owner/admin only — a manager or delivery hire must not spend the
# owner's money. Same ownership check as every other dashboard route.
RequireOwner = require_role("shop_owner", "admin")


async def _invalidate_shop_caches(shop_id) -> None:
    await invalidate("shops:list", f"shop:{shop_id}")


@router.get("/plans", response_model=PlansResponse)
async def list_plans(user: Profile = Depends(RequireOwner), db: AsyncSession = Depends(get_db)):
    plans = (
        await db.execute(
            select(SponsorshipPlan).where(SponsorshipPlan.is_active.is_(True)).order_by(SponsorshipPlan.sort_order)
        )
    ).scalars().all()
    mode = payment_mode()
    return PlansResponse(
        mode=mode,
        razorpay_key_id=settings.razorpay_key_id if mode == "razorpay" else None,
        plans=[PlanOut.model_validate(p) for p in plans],
    )


@router.get("/shops/{shop_id}", response_model=SponsorshipStatus)
async def sponsorship_status(
    shop_id: str, user: Profile = Depends(RequireOwner), db: AsyncSession = Depends(get_db)
):
    shop = await _get_owned_shop_or_403(parse_uuid_or_404(shop_id, "Shop"), user, db)
    purchases = (
        await db.execute(
            select(SponsorshipPurchase)
            .where(SponsorshipPurchase.shop_id == shop.id, SponsorshipPurchase.status == "paid")
            .order_by(SponsorshipPurchase.paid_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return SponsorshipStatus(
        is_sponsored=shop.is_sponsored,
        sponsored_until=shop.sponsored_until,
        purchases=[PurchaseOut.model_validate(p) for p in purchases],
    )


@router.post("/shops/{shop_id}/checkout", response_model=CheckoutResponse)
async def start_checkout(
    shop_id: str,
    payload: CheckoutRequest,
    user: Profile = Depends(RequireOwner),
    db: AsyncSession = Depends(get_db),
):
    """Step 1 of buying: records a pending purchase at the plan's CURRENT
    price (looked up here, never taken from the client) and, in Razorpay
    mode, creates the Razorpay order the checkout popup will pay."""
    shop = await _get_owned_shop_or_403(parse_uuid_or_404(shop_id, "Shop"), user, db)
    if shop.approval_status != "approved" or not shop.is_active:
        raise HTTPException(status_code=400, detail="Only approved, active shops can be sponsored")

    mode = payment_mode()
    if mode is None:
        raise HTTPException(status_code=503, detail="Sponsorship payments aren't configured on this server")

    plan = await db.get(SponsorshipPlan, payload.plan_key)
    if plan is None or not plan.is_active:
        raise HTTPException(status_code=404, detail="Plan not found")

    purchase = SponsorshipPurchase(
        id=uuid.uuid4(),
        shop_id=shop.id,
        purchased_by=user.id,
        plan_key=plan.key,
        plan_name=plan.name,
        days=plan.days,
        amount=plan.price,
        status="created",
        provider=mode,
    )
    resp = CheckoutResponse(
        purchase_id=purchase.id, mode=mode, amount=plan.price, plan_name=plan.name
    )

    if mode == "razorpay":
        amount_paise = int(round(float(plan.price) * 100))
        try:
            order = await create_razorpay_order(amount_paise, receipt=str(purchase.id))
        except Exception:
            raise HTTPException(status_code=502, detail="Couldn't start the payment — please try again")
        purchase.provider_order_id = order["id"]
        resp.razorpay_key_id = settings.razorpay_key_id
        resp.razorpay_order_id = order["id"]
        resp.amount_paise = amount_paise

    db.add(purchase)
    await db.commit()
    return resp


@router.post("/shops/{shop_id}/confirm", response_model=SponsorshipStatus)
async def confirm_purchase(
    shop_id: str,
    payload: ConfirmRequest,
    user: Profile = Depends(RequireOwner),
    db: AsyncSession = Depends(get_db),
):
    """Step 2: the browser reports a finished payment. In Razorpay mode we
    only activate after the signature verifies against our secret — the
    client's word alone is never enough. Test mode (local dev only, see
    payment_mode()) activates without a signature."""
    shop = await _get_owned_shop_or_403(parse_uuid_or_404(shop_id, "Shop"), user, db)
    purchase = await db.get(SponsorshipPurchase, payload.purchase_id)
    if purchase is None or purchase.shop_id != shop.id:
        raise HTTPException(status_code=404, detail="Purchase not found")

    if purchase.status != "paid":
        if purchase.provider == "razorpay":
            if not (
                payload.razorpay_payment_id
                and payload.razorpay_signature
                and purchase.provider_order_id
                and verify_checkout_signature(
                    purchase.provider_order_id, payload.razorpay_payment_id, payload.razorpay_signature
                )
            ):
                raise HTTPException(status_code=400, detail="Payment couldn't be verified")
        elif payment_mode() != "test":
            # A "test" purchase can only exist when the server was in test
            # mode; refuse to honor one if that's no longer the case.
            raise HTTPException(status_code=400, detail="Test payments are disabled")

        await activate_purchase(db, purchase.id, payload.razorpay_payment_id)
        await db.commit()
        await _invalidate_shop_caches(shop.id)

    await db.refresh(shop)
    return await sponsorship_status(str(shop.id), user, db)


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
):
    """Razorpay -> us, server to server. Activates a purchase even if the
    buyer closed the tab right after paying. Signature-verified; opens
    its own session (no logged-in user here)."""
    body = await request.body()
    if not verify_webhook_signature(body, x_razorpay_signature or ""):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event = json.loads(body)
    if event.get("event") != "payment.captured":
        return {"received": True}
    entity = event.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = entity.get("order_id")
    if not order_id:
        return {"received": True}

    async with AsyncSessionLocal() as db:
        purchase = (
            await db.execute(
                select(SponsorshipPurchase).where(SponsorshipPurchase.provider_order_id == order_id)
            )
        ).scalar_one_or_none()
        if purchase is not None:
            await activate_purchase(db, purchase.id, entity.get("id"))
            await db.commit()
            await _invalidate_shop_caches(purchase.shop_id)
    return {"received": True}
