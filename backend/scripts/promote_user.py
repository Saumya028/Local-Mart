"""
Promotes a user's role directly in the database.

Becoming a shop_owner is deliberately NOT self-service — a plain customer
account cannot create a shop or reach the Shop Dashboard on their own
(see routers/shops.py and routers/shop_dashboard.py, both gated with
require_role("shop_owner", "admin")). Someone has to be promoted first.

Until Phase 6 ships an Admin Panel with a real "approve this seller" UI,
this script is that promotion step — run it locally by whoever's acting
as the platform operator during development.

Usage (from backend/, with your virtualenv active and .env configured):

    python -m scripts.promote_user someone@example.com shop_owner

The user must have logged in at least once already — a profile row only
exists after their first authenticated request (see
core/security.py's get_current_user, which auto-creates it on first
login as role="customer").
"""
import asyncio
import sys

from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models import Profile

VALID_ROLES = {"customer", "shop_owner", "admin"}


async def promote(email: str, role: str) -> None:
    if role not in VALID_ROLES:
        print(f'"{role}" isn\'t a recognized role. Valid roles: {", ".join(sorted(VALID_ROLES))}')
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Profile).where(Profile.email == email))
        profile = result.scalar_one_or_none()

        if profile is None:
            print(
                f"No profile found for {email}. They need to log in at least once first — "
                f"a profile row is created automatically on their first authenticated request."
            )
            return

        old_role = profile.role
        profile.role = role
        await db.commit()
        print(f"Updated {email}: {old_role} -> {role}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python -m scripts.promote_user <email> <role>")
        print("Example: python -m scripts.promote_user seller@example.com shop_owner")
        sys.exit(1)

    asyncio.run(promote(sys.argv[1], sys.argv[2]))
