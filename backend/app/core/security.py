import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.models import Profile

bearer_scheme = HTTPBearer(auto_error=False)

# Lazily created on first use, then reused — PyJWKClient caches the fetched
# public keys internally so we're not hitting Supabase's JWKS endpoint on
# every single request.
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url)
    return _jwks_client


def decode_supabase_token(token: str) -> dict:
    """
    Verifies a Supabase-issued JWT.

    Supabase projects sign tokens one of two ways, depending on when the
    project was created / its settings:
      - Legacy: HS256, signed with a shared secret (SUPABASE_JWT_SECRET).
      - Current default: ES256, signed with an asymmetric key pair, where
        we verify using Supabase's PUBLIC key, fetched from its JWKS
        endpoint (no secret to store at all for this path).

    We read the `alg` out of the token's own header and branch on it, so
    this works correctly regardless of which scheme your specific
    Supabase project uses — you don't have to know or configure which one
    it is.

    `leeway=10` gives a 10-second tolerance on the token's time-based
    claims (iat/exp). Without this, small clock drift between your machine
    and Supabase's servers causes intermittent, hard-to-explain 401s —
    e.g. "the token is not yet valid" even for a token that was issued a
    moment ago. This doesn't weaken security meaningfully; it just accepts
    that no two machines' clocks are perfectly in sync.

    We only ever trust this token for WHO the user is (`sub`, `email`) —
    never for role/permissions (see get_current_user below).
    """
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "HS256":
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
                leeway=10,
            )

        # Asymmetric (ES256/RS256): fetch Supabase's public signing key
        # matching this token's `kid` and verify against that.
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            audience="authenticated",
            leeway=10,
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    """
    The dependency every protected route uses:

        @router.get("/something")
        async def route(user: Profile = Depends(get_current_user)):
            ...

    Steps:
    1. Verify the JWT Supabase issued -> get the user's id + email.
    2. Look up (or create, on first login) their row in our `profiles`
       table -> this is where their ROLE lives, which the JWT itself
       never gets to decide.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_supabase_token(credentials.credentials)
    user_id = uuid.UUID(payload["sub"])
    email = payload.get("email")

    result = await db.execute(select(Profile).where(Profile.id == user_id))
    profile = result.scalar_one_or_none()

    if profile is None:
        # First time this user has ever called our API — auto-provision a
        # default "customer" profile row. Becoming a shop_owner or admin
        # always happens through a separate, explicit action later, never
        # through this path.
        profile = Profile(id=user_id, email=email, role="customer")
        db.add(profile)
        await db.commit()
        await db.refresh(profile)

    return profile


def require_role(*allowed_roles: str):
    """
    Use on any route that only certain roles should reach, e.g.:

        @router.post("/shops")
        async def create_shop(user: Profile = Depends(require_role("shop_owner", "admin"))):
            ...
    """

    async def checker(user: Profile = Depends(get_current_user)) -> Profile:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="You don't have permission to do this")
        return user

    return checker
