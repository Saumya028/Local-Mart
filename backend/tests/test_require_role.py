"""
require_role() is the single dependency EVERY ownership/role check in
the app is built on (shop_dashboard.py, admin.py, POST /shops). The
roadmap calls this out twice — once for Phase 1 ("write 3-5 tests
here... auth bugs are the ones that actually hurt you") and again for
Phase 6 ("admin routes are the highest-value target for privilege
escalation bugs — test role checks here harder than anywhere else").
Neither ever actually got a test written against it until now — worth
being upfront about that gap (see backend/README.md) rather than
implying it was always covered.

These call the dependency's inner `checker` function directly with a
plain Python object standing in for a Profile, rather than going
through FastAPI's DI or a real database — require_role's own logic
never touches the DB (that's get_current_user's job, tested
separately would need a real Supabase JWT), so this is enough to prove
the actual role-comparison logic is correct in isolation.
"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core.security import require_role


def _fake_user(role: str):
    return SimpleNamespace(id="00000000-0000-0000-0000-000000000000", role=role)


@pytest.mark.asyncio
async def test_allows_a_role_in_the_allowed_list():
    checker = require_role("shop_owner", "admin")
    user = _fake_user("shop_owner")
    assert await checker(user=user) is user


@pytest.mark.asyncio
async def test_allows_every_role_in_a_multi_role_list():
    checker = require_role("shop_owner", "admin")
    user = _fake_user("admin")
    assert await checker(user=user) is user


@pytest.mark.asyncio
async def test_rejects_a_role_not_in_the_allowed_list():
    checker = require_role("admin")
    user = _fake_user("customer")
    with pytest.raises(HTTPException) as exc_info:
        await checker(user=user)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_shop_owner_cannot_reach_an_admin_only_route():
    # The exact scenario admin.py's whole router depends on: a
    # shop_owner is a legitimate, privileged role elsewhere in the app,
    # but must still be refused here.
    checker = require_role("admin")
    user = _fake_user("shop_owner")
    with pytest.raises(HTTPException) as exc_info:
        await checker(user=user)
    assert exc_info.value.status_code == 403
