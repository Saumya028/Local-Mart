"""
Calls Supabase's Admin REST API (/auth/v1/admin/users) using the
service_role key — the ONE place this app ever creates or removes a
login without the person signing themselves up. Everywhere else, an
account is created by the person themselves via the frontend's normal
supabase.auth.signUp()/signInWithPassword() calls, which this backend
never sees a password for.

A shop owner creating a manager/delivery account is different: the
staff member doesn't self-signup, so the owner (who already knows the
email/password they're handing the person) provisions it directly from
the Staff tab. This module is what actually talks to Supabase for that
one flow — see routers/shop_dashboard.py's staff endpoints.
"""

import httpx
from fastapi import HTTPException

from app.core.config import settings


def _admin_headers() -> dict[str, str]:
    if not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=500,
            detail=(
                "Staff account creation isn't configured on this server yet — "
                "SUPABASE_SERVICE_ROLE_KEY is missing from the backend's environment."
            ),
        )
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


async def create_supabase_user(email: str, password: str, full_name: str) -> str:
    """
    Creates a real Supabase Auth user and returns its id (a uuid string) —
    this becomes the new profiles.id, exactly like every other account.

    `email_confirm: True` skips Supabase's usual confirmation-email step.
    That's deliberate here specifically: the shop OWNER is vouching for
    this address (it's their employee's), not the account holder proving
    they own it themselves — the same trust relationship as, say, a
    company handing a new hire their work email and its first password.
    """
    url = f"{settings.supabase_url}/auth/v1/admin/users"
    payload = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {"full_name": full_name},
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(url, headers=_admin_headers(), json=payload)
        except httpx.HTTPError:
            raise HTTPException(
                status_code=502, detail="Couldn't reach Supabase to create this staff account."
            )

    if resp.status_code in (400, 422):
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        detail = body.get("msg") or body.get("error_description") or body.get("message")
        # Supabase's own message for a duplicate email is clear enough to
        # show directly — no need to reword it.
        raise HTTPException(status_code=400, detail=detail or "Couldn't create this staff account.")
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail="Couldn't reach Supabase to create this staff account.")

    return resp.json()["id"]


async def delete_supabase_user(user_id: str) -> None:
    """
    Used when an owner removes a staff member for good — revokes their
    login at the source rather than just hiding them in our own
    database. Deliberately swallows a missing-key config or a failure
    here rather than raising: the caller (routers/shop_dashboard.py)
    always deletes the local profiles/shop_staff rows regardless, since
    an owner clicking "Remove" expects the person to disappear from
    their Staff tab even if, say, Supabase is briefly unreachable.
    """
    if not settings.supabase_service_role_key:
        return
    url = f"{settings.supabase_url}/auth/v1/admin/users/{user_id}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.delete(url, headers=_admin_headers())
        except httpx.HTTPError:
            pass


async def update_supabase_user_password(user_id: str, new_password: str) -> None:
    """Owner-initiated password reset for a staff account (Staff tab's
    "Reset password" action) — there's no "forgot password" email flow
    for staff, since they didn't sign up with an email Supabase can
    treat as verified-by-them in the first place."""
    url = f"{settings.supabase_url}/auth/v1/admin/users/{user_id}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.put(url, headers=_admin_headers(), json={"password": new_password})
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="Couldn't reach Supabase to reset this password.")
    if resp.status_code >= 400:
        raise HTTPException(status_code=400, detail="Couldn't reset this staff member's password.")
