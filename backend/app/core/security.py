import logging
import uuid

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core import customer_validation as cv
from app.models import Address, Profile

logger = logging.getLogger(__name__)

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


def profile_details_from_metadata(metadata: dict) -> dict:
    """
    Pull the extra signup fields (DOB, gender, phone, business/GST details)
    out of the JWT's `user_metadata`.

    user_metadata is chosen by the client at signUp(), so it's treated as
    untrusted input: each field goes through the same validator the API
    uses, and a bad value is just dropped (never raised) so a typo can't
    lock someone out of logging in — they can fix it under My Account.
    `gst_verified` is never read from here for the same reason.
    """
    details: dict = {}
    for key, fn in (
        ("phone", cv.validate_phone),
        ("date_of_birth", cv.validate_dob),
        ("gender", cv.validate_gender),
    ):
        value = cv.safe(fn, metadata.get(key))
        if value is not None:
            details[key] = value

    if cv.safe(cv.validate_customer_type, metadata.get("customer_type")) == "business":
        business_name = cv.safe(lambda v: cv.clean_text(v, field="Business name", max_len=150), metadata.get("business_name"))
        gstin = cv.safe(cv.validate_gstin, metadata.get("gstin"))
        pan = cv.safe(cv.validate_pan, metadata.get("pan"))
        # Only become a business account if the details that make it one
        # are actually valid; otherwise stay a normal customer.
        if business_name and gstin and (pan is None or pan == cv.pan_from_gstin(gstin)):
            details.update(customer_type="business", business_name=business_name, gstin=gstin, pan=pan)
    return details


def first_address_from_metadata(metadata: dict, fallback_name: str | None) -> dict | None:
    """The delivery address typed on the signup form, if complete and valid."""
    raw = metadata.get("address")
    if not isinstance(raw, dict):
        return None
    try:
        from app.schemas.address import AddressCreate

        data = AddressCreate(
            label=raw.get("label") or "Home",
            recipient_name=raw.get("recipient_name") or fallback_name,
            phone=raw.get("phone") or metadata.get("phone"),
            line1=raw.get("line1"),
            line2=raw.get("line2"),
            landmark=raw.get("landmark"),
            city=raw.get("city"),
            state=raw.get("state"),
            pincode=raw.get("pincode"),
        )
    except Exception:
        return None
    return data.model_dump(exclude={"is_default", "lat", "lng"})


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
        #
        # `phone` and `full_name` come straight from the JWT so a
        # phone-only Login (see the Phone tab) or a Signup that collected
        # a name don't end up as a bare, unnamed row — Supabase includes
        # the phone number as its own top-level claim for phone-verified
        # users, and echoes back whatever was passed as `options.data` at
        # signUp() under `user_metadata`.
        phone = payload.get("phone") or None
        metadata = payload.get("user_metadata") or {}
        full_name = metadata.get("full_name")
        details = profile_details_from_metadata(metadata)
        # An email signup has no JWT `phone` claim; its mobile number
        # rides in user_metadata instead.
        profile = Profile(
            id=user_id,
            email=email,
            phone=phone or details.pop("phone", None),
            full_name=full_name,
            role="customer",
            **{k: v for k, v in details.items() if k != "phone"},
        )
        db.add(profile)
        # Flush (INSERT the profile row) BEFORE adding the address: the
        # models declare the addresses.user_id foreign key but no ORM
        # relationship(), so SQLAlchemy doesn't know to order the two
        # INSERTs and may send the address first -> a foreign-key
        # violation that would 500 every request for this new user.
        await db.flush()
        first_address = first_address_from_metadata(metadata, fallback_name=full_name)
        if first_address is not None:
            # A SAVEPOINT, so a problem with this optional extra can
            # never roll back the profile itself or block the login.
            try:
                async with db.begin_nested():
                    db.add(Address(id=uuid.uuid4(), user_id=user_id, is_default=True, **first_address))
            except Exception:
                logger.warning("Could not save signup address for user %s", user_id, exc_info=True)
        await db.commit()
        await db.refresh(profile)

    # A suspended account (Admin Panel > Manage Users > Suspend) is locked
    # out here, on the very next request — not just hidden from the UI.
    # This is the actual enforcement; the frontend's "Suspend" button is
    # just how an admin flips this flag.
    if profile.is_suspended:
        raise HTTPException(status_code=403, detail="This account has been suspended")

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
