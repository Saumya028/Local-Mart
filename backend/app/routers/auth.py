from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.models import Profile
from app.schemas.profile import ProfileOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=ProfileOut)
async def get_me(current_user: Profile = Depends(get_current_user)):
    """
    Returns the logged-in user's profile.

    This is the endpoint the frontend calls right after login to confirm
    the token actually works end to end: browser has a Supabase session ->
    sends the JWT -> FastAPI verifies it -> looks up (or creates) the
    profile row -> returns it. If this works, auth is fully wired.
    """
    return current_user
