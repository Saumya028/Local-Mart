from fastapi import APIRouter, Depends

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
    """My Account > Settings — edits full_name/phone only (see ProfileUpdate's docstring for what's deliberately excluded and why)."""
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, key, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user
