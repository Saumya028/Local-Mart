from fastapi import APIRouter, Depends, HTTPException

from app.core import customer_validation as cv
from app.core.db import get_db
from app.core.rate_limit import rate_limit_by_ip
from app.core.security import get_current_user
from app.models import Profile
from app.schemas.profile import ProfileOut, ProfileUpdate
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/me",
    response_model=ProfileOut,
    dependencies=[Depends(rate_limit_by_ip("auth_me", limit=30, window_seconds=60))],
)
async def get_me(current_user: Profile = Depends(get_current_user)):
    """
    Returns the logged-in user's profile.

    This is the endpoint the frontend calls right after login to confirm
    the token actually works end to end: browser has a Supabase session ->
    sends the JWT -> FastAPI verifies it -> looks up (or creates) the
    profile row -> returns it. If this works, auth is fully wired.

    Real credential checking (the actual login/signup form) happens
    entirely in Supabase Auth, which the frontend calls directly — this
    backend never sees a password, so there's no login endpoint here to
    brute-force in the traditional sense. This IS the one auth-adjacent
    endpoint this backend owns, though: it verifies a JWT and does a DB
    lookup/insert on every call, so it's rate-limited by IP (30/min) to
    blunt a flood of garbage or stolen-token requests before they cost a
    JWKS fetch and a database round trip each.
    """
    return current_user


@router.patch("/me", response_model=ProfileOut)
async def update_me(
    payload: ProfileUpdate,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    My Account > Settings — edits the customer's own details (name, phone,
    DOB, gender, account type and business/GST details). See ProfileUpdate's
    docstring for what's deliberately excluded and why.
    """
    updates = payload.model_dump(exclude_unset=True)

    # full_name can be cleared by an explicit null elsewhere in the app,
    # but customer_type is NOT NULL — ignore an explicit null for it.
    if updates.get("customer_type") is None:
        updates.pop("customer_type", None)

    old_gstin = current_user.gstin
    for key, value in updates.items():
        setattr(current_user, key, value)

    if current_user.customer_type == "business":
        if not current_user.business_name:
            raise HTTPException(status_code=422, detail="Business name is required for a business account")
        if not current_user.gstin:
            raise HTTPException(status_code=422, detail="GSTIN is required for a business account")
        # A GSTIN embeds the holder's PAN (characters 3-12) — if both were
        # given they have to agree, which catches most typos for free.
        if current_user.pan and current_user.pan != cv.pan_from_gstin(current_user.gstin):
            raise HTTPException(status_code=422, detail="PAN doesn't match the PAN inside the GSTIN")
        # A different GSTIN is a different (unverified) claim.
        if current_user.gstin != old_gstin:
            current_user.gst_verified = False
    else:
        # Back to a normal customer: the business details no longer apply,
        # and GST treatment must not linger on the account.
        current_user.business_name = None
        current_user.gstin = None
        current_user.pan = None
        current_user.gst_verified = False

    await db.commit()
    await db.refresh(current_user)
    return current_user
