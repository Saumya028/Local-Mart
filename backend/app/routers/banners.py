import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.security import require_role
from app.core.sponsorship import (
    activate_banner_payment,
    create_razorpay_order,
    payment_mode,
    verify_checkout_signature,
)
from app.core.utils import parse_uuid_or_404
from app.models import Banner, BannerPayment, BannerSlot, PlatformSettings, Profile, Shop
from app.routers.shop_dashboard import _get_owned_shop_or_403
from app.routers.shops import _distance_expr
from app.schemas.banner import (
    BannerCheckoutResponse,
    BannerConfirm,
    BannerCreate,
    OwnerBannerOut,
    PublicBannerOut,
    SlotOut,
    SlotsResponse,
)

router = APIRouter(prefix="/banners", tags=["banners"])
RequireOwner = require_role("shop_owner", "admin")

# At most this many banners are returned for one slot + location; the
# frontend rotates through them.
MAX_PER_SLOT = 5


def owner_banner_out(banner: Banner, slot: BannerSlot) -> OwnerBannerOut:
    return OwnerBannerOut(
        id=banner.id,
        slot_key=slot.key,
        slot_name=slot.name,
        width=slot.width,
        height=slot.height,
        price=slot.price,
        duration_days=slot.duration_days,
        image_url=banner.image_url,
        title=banner.title,
        state=banner.state,
        rejection_reason=banner.rejection_reason,
        starts_at=banner.starts_at,
        ends_at=banner.ends_at,
        impressions=banner.impressions,
        clicks=banner.clicks,
        created_at=banner.created_at,
    )


# ---------------------------------------------------------------- public


@router.get("/public", response_model=list[PublicBannerOut])
async def public_banners(
    slot: str = Query(...),
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    db: AsyncSession = Depends(get_db),
):
    """
    The banners a customer at (lat, lng) may see for one slot: approved,
    paid-up (ends_at in the future), from active approved shops located
    within the platform's banner radius of the viewer. Distance is checked
    HERE, in SQL — never in the browser — so a customer outside a shop's
    locality can't see (or even receive) that shop's banner. The viewer's
    coordinates are used for this one query and not stored or logged.
    Not cached: the answer is per-location. Also counts an impression for
    each banner served.
    """
    settings_row = await db.get(PlatformSettings, 1)
    radius = float(settings_row.banner_radius_km) if settings_row else 1.0
    distance = _distance_expr(lat, lng)

    rows = (
        await db.execute(
            select(Banner, Shop.name, BannerSlot.width, BannerSlot.height)
            .join(Shop, Shop.id == Banner.shop_id)
            .join(BannerSlot, BannerSlot.key == Banner.slot_key)
            .where(
                Banner.slot_key == slot,
                BannerSlot.is_active.is_(True),
                Banner.review_status == "approved",
                Banner.ends_at > func.now(),
                Shop.is_active.is_(True),
                Shop.approval_status == "approved",
                Shop.latitude.isnot(None),
                Shop.longitude.isnot(None),
                distance <= radius,
            )
            .order_by(func.random())
            .limit(MAX_PER_SLOT)
        )
    ).all()

    if rows:
        await db.execute(
            update(Banner).where(Banner.id.in_([r[0].id for r in rows])).values(impressions=Banner.impressions + 1)
        )
        await db.commit()

    return [
        PublicBannerOut(
            id=b.id, image_url=b.image_url, title=b.title, shop_id=b.shop_id, shop_name=shop_name, width=w, height=h
        )
        for b, shop_name, w, h in rows
    ]


@router.post("/{banner_id}/click")
async def banner_click(banner_id: str, db: AsyncSession = Depends(get_db)):
    """Counts a click on a live banner (the browser then opens the shop)."""
    bid = parse_uuid_or_404(banner_id, "Banner")
    await db.execute(
        update(Banner)
        .where(Banner.id == bid, Banner.review_status == "approved", Banner.ends_at > func.now())
        .values(clicks=Banner.clicks + 1)
    )
    await db.commit()
    return {"ok": True}


# ----------------------------------------------------------------- owner


@router.get("/slots", response_model=SlotsResponse)
async def list_slots(user: Profile = Depends(RequireOwner), db: AsyncSession = Depends(get_db)):
    slots = (
        await db.execute(select(BannerSlot).where(BannerSlot.is_active.is_(True)).order_by(BannerSlot.sort_order))
    ).scalars().all()
    mode = payment_mode()
    return SlotsResponse(
        mode=mode,
        razorpay_key_id=settings.razorpay_key_id if mode == "razorpay" else None,
        slots=[SlotOut.model_validate(s) for s in slots],
    )


@router.get("/shops/{shop_id}", response_model=list[OwnerBannerOut])
async def my_banners(shop_id: str, user: Profile = Depends(RequireOwner), db: AsyncSession = Depends(get_db)):
    shop = await _get_owned_shop_or_403(parse_uuid_or_404(shop_id, "Shop"), user, db)
    rows = (
        await db.execute(
            select(Banner, BannerSlot)
            .join(BannerSlot, BannerSlot.key == Banner.slot_key)
            .where(Banner.shop_id == shop.id)
            .order_by(Banner.created_at.desc())
        )
    ).all()
    return [owner_banner_out(b, s) for b, s in rows]


@router.post("/shops/{shop_id}", response_model=OwnerBannerOut, status_code=201)
async def request_banner(
    shop_id: str,
    payload: BannerCreate,
    user: Profile = Depends(RequireOwner),
    db: AsyncSession = Depends(get_db),
):
    """Step 1: the owner asks for a banner. Goes to admin review; nothing
    is charged yet (payment opens once an admin approves the artwork)."""
    shop = await _get_owned_shop_or_403(parse_uuid_or_404(shop_id, "Shop"), user, db)
    if shop.approval_status != "approved" or not shop.is_active:
        raise HTTPException(status_code=400, detail="Only approved, active shops can request banners")
    if shop.latitude is None or shop.longitude is None:
        raise HTTPException(
            status_code=400,
            detail="Set your shop's location first — banners are shown only to customers near your shop",
        )
    if not payload.image_url.lower().startswith(("https://", "http://")):
        raise HTTPException(status_code=422, detail="Banner image must be an uploaded image URL")

    slot = await db.get(BannerSlot, payload.slot_key)
    if slot is None or not slot.is_active:
        raise HTTPException(status_code=404, detail="That banner spot isn't available")

    # One open banner per shop per slot (pending / awaiting payment / live).
    existing = (
        await db.execute(select(Banner).where(Banner.shop_id == shop.id, Banner.slot_key == slot.key))
    ).scalars().all()
    if any(b.state in ("pending", "awaiting_payment", "live") for b in existing):
        raise HTTPException(
            status_code=409,
            detail="You already have an open banner for this spot. Withdraw it or wait for it to end.",
        )

    banner = Banner(
        id=uuid.uuid4(),
        shop_id=shop.id,
        slot_key=slot.key,
        image_url=payload.image_url,
        title=(payload.title or "").strip() or None,
        review_status="pending",
    )
    db.add(banner)
    await db.commit()
    await db.refresh(banner)
    return owner_banner_out(banner, slot)


async def _owned_banner(banner_id: str, user: Profile, db: AsyncSession) -> tuple[Banner, BannerSlot]:
    bid = parse_uuid_or_404(banner_id, "Banner")
    banner = await db.get(Banner, bid)
    if banner is None:
        raise HTTPException(status_code=404, detail="Banner not found")
    await _get_owned_shop_or_403(banner.shop_id, user, db)
    slot = await db.get(BannerSlot, banner.slot_key)
    return banner, slot


@router.delete("/{banner_id}")
async def withdraw_banner(banner_id: str, user: Profile = Depends(RequireOwner), db: AsyncSession = Depends(get_db)):
    """Owner removes a request that isn't running. A LIVE (paid) banner
    can't be withdrawn here — it stays up for the term that was paid for;
    admin can take it down for policy reasons."""
    banner, _slot = await _owned_banner(banner_id, user, db)
    if banner.state == "live":
        raise HTTPException(status_code=409, detail="This banner is live — it runs until its end date")
    await db.delete(banner)
    await db.commit()
    return {"ok": True}


@router.post("/{banner_id}/checkout", response_model=BannerCheckoutResponse)
async def banner_checkout(
    banner_id: str, user: Profile = Depends(RequireOwner), db: AsyncSession = Depends(get_db)
):
    """Step 3 (after admin approval) — also used to RENEW: opens a payment
    at the slot's CURRENT price (server-side lookup, never from the
    client). A renewal of an unchanged, approved banner needs no new
    review."""
    banner, slot = await _owned_banner(banner_id, user, db)
    if banner.review_status != "approved":
        raise HTTPException(status_code=400, detail="This banner hasn't been approved yet")
    if not slot.is_active:
        raise HTTPException(status_code=400, detail="That banner spot isn't available right now")
    mode = payment_mode()
    if mode is None:
        raise HTTPException(status_code=503, detail="Payments aren't configured on this server")

    payment = BannerPayment(
        id=uuid.uuid4(),
        banner_id=banner.id,
        purchased_by=user.id,
        days=slot.duration_days,
        amount=slot.price,
        status="created",
        provider=mode,
    )
    resp = BannerCheckoutResponse(payment_id=payment.id, mode=mode, amount=slot.price)
    if mode == "razorpay":
        amount_paise = int(round(float(slot.price) * 100))
        try:
            order = await create_razorpay_order(amount_paise, receipt=str(payment.id))
        except Exception:
            raise HTTPException(status_code=502, detail="Couldn't start the payment — please try again")
        payment.provider_order_id = order["id"]
        resp.razorpay_key_id = settings.razorpay_key_id
        resp.razorpay_order_id = order["id"]
        resp.amount_paise = amount_paise
    db.add(payment)
    await db.commit()
    return resp


@router.post("/{banner_id}/confirm", response_model=OwnerBannerOut)
async def banner_confirm(
    banner_id: str,
    payload: BannerConfirm,
    user: Profile = Depends(RequireOwner),
    db: AsyncSession = Depends(get_db),
):
    banner, slot = await _owned_banner(banner_id, user, db)
    payment = await db.get(BannerPayment, payload.payment_id)
    if payment is None or payment.banner_id != banner.id:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != "paid":
        if payment.provider == "razorpay":
            if not (
                payload.razorpay_payment_id
                and payload.razorpay_signature
                and payment.provider_order_id
                and verify_checkout_signature(
                    payment.provider_order_id, payload.razorpay_payment_id, payload.razorpay_signature
                )
            ):
                raise HTTPException(status_code=400, detail="Payment couldn't be verified")
        elif payment_mode() != "test":
            raise HTTPException(status_code=400, detail="Test payments are disabled")
        await activate_banner_payment(db, payment.id, payload.razorpay_payment_id)
        await db.commit()
        await db.refresh(banner)
    return owner_banner_out(banner, slot)
