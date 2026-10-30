import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core import customer_validation as cv
from app.core.shop_hours import normalize_opening_hours, validate_timezone
from app.core.upi import is_valid_upi_id, normalize_upi_id

SLOT_LENGTHS = (15, 30, 45, 60, 90, 120, 180, 240)

# Kept in sync by hand with admin.py's VALID_DOCS_STATUSES:
# "pending"   — no documents on file yet, or an admin has explicitly
#                requested new/additional ones (see routers/admin.py's
#                request_shop_docs) and is waiting on the owner.
# "submitted" — the owner has uploaded document(s) and it's now the
#                admin's turn to review them.
# "verified"  — an admin has reviewed and accepted the documents.
VALID_DOCS_STATUSES = ("pending", "submitted", "verified")


class ShopDocument(BaseModel):
    name: str  # human label, e.g. "GST Certificate"
    doc_type: str  # e.g. "gst_certificate", "id_proof", "address_proof", "other"
    url: str  # Supabase Storage URL — see frontend/lib/documentUpload.ts


class ShopCreate(BaseModel):
    name: str
    category: str
    # Selling isn't self-service (see routers/shops.py's create_shop
    # docstring), and neither is skipping verification: an application
    # with zero documents attached isn't reviewable, so the platform
    # would have nothing to approve against. This is what actually closes
    # the gap a real test run found — a shop used to become fully
    # operable the instant this endpoint returned, with nothing uploaded
    # and nothing blocking it.
    documents: list[ShopDocument]
    # Required from here on (see migration 0009) — without these, a shop
    # can never appear in a customer's "near me" search, which is the
    # whole point of a *local* marketplace. address_line1/city are typed
    # by the applicant; latitude/longitude come from the browser's
    # Geolocation API on the apply form (see frontend/app/shop/dashboard).
    address_line1: str
    city: str
    latitude: float
    longitude: float
    # Category-specific fields defined by an admin (e.g. a pharmacy's
    # drug license number) — see Shop.attributes and
    # core/attribute_validation.py. Validated in routers/shops.py's
    # create_shop against AttributeSchema(kind="shop") for the chosen
    # category; {} is fine for a category with no schema defined.
    attributes: dict = {}

    # Customers (and the platform, for the shop's own order issues) need a
    # way to reach the shop: required to apply.
    contact_phone: str
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("contact_phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        cleaned = cv.validate_phone(v)
        if cleaned is None:
            raise ValueError("A contact phone number is required")
        return cleaned

    @field_validator("description")
    @classmethod
    def _about(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v else None

    @field_validator("documents")
    @classmethod
    def at_least_one_document(cls, v: list[ShopDocument]) -> list[ShopDocument]:
        if len(v) < 1:
            raise ValueError(
                "At least one verification document (e.g. a business "
                "registration certificate or owner ID proof) is required to apply."
            )
        return v

    @field_validator("latitude")
    @classmethod
    def lat_in_range(cls, v: float) -> float:
        if not -90 <= v <= 90:
            raise ValueError("latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def lng_in_range(cls, v: float) -> float:
        if not -180 <= v <= 180:
            raise ValueError("longitude must be between -180 and 180")
        return v


class ShopUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    is_active: bool | None = None
    # "Pick up from the shop" toggle — see Shop.pickup_enabled.
    pickup_enabled: bool | None = None
    address_line1: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    # Category-specific fields (e.g. a pharmacy's drug license number) —
    # see Shop.attributes and core/attribute_validation.py.
    attributes: dict | None = None
    # Direct payments — see Shop.upi_id etc. An empty string clears the
    # UPI id / QR.
    upi_id: str | None = None
    upi_qr_url: str | None = None
    accepts_upi: bool | None = None
    accepts_cash: bool | None = None
    # Lets an owner resubmit documents after a rejection or a
    # "Request Docs" admin action, via the SAME endpoint
    # (PUT /dashboard/shops/{id}) rather than a separate one — see that
    # route's handling: setting this also flips docs_status back to
    # "submitted" and clears any prior rejection_reason.
    documents: list[ShopDocument] | None = None

    # ---- profile -------------------------------------------------------
    contact_phone: str | None = None
    description: str | None = Field(default=None, max_length=1000)
    # ---- hours & closure ------------------------------------------------
    # null clears the schedule (= always open); see core/shop_hours.py.
    opening_hours: dict | None = None
    timezone: str | None = None
    temporarily_closed: bool | None = None
    closed_until: datetime | None = None
    closed_message: str | None = Field(default=None, max_length=140)
    # ---- delivery pricing (delivery orders only) -------------------------
    delivery_fee: Decimal | None = Field(default=None, ge=0, le=5000, decimal_places=2)
    free_delivery_above: Decimal | None = Field(default=None, ge=0, le=1_000_000, decimal_places=2)
    min_order_amount: Decimal | None = Field(default=None, ge=0, le=1_000_000, decimal_places=2)
    # ---- timing ----------------------------------------------------------
    prep_time_minutes: int | None = Field(default=None, ge=0, le=720)
    delivery_time_minutes: int | None = Field(default=None, ge=0, le=720)
    slots_enabled: bool | None = None
    slot_length_minutes: int | None = None
    slot_capacity: int | None = Field(default=None, ge=1, le=500)
    slot_days_ahead: int | None = Field(default=None, ge=1, le=7)
    # ---- inventory ---------------------------------------------------------
    low_stock_threshold: int | None = Field(default=None, ge=0, le=100_000)
    # ---- GST / invoicing (blank clears) --------------------------------------
    gstin: str | None = None
    legal_name: str | None = Field(default=None, max_length=150)

    @field_validator("gstin")
    @classmethod
    def _gstin(cls, v: str | None) -> str | None:
        return cv.validate_gstin(v)

    @field_validator("legal_name")
    @classmethod
    def _legal_name(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v else None

    @field_validator("contact_phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return cv.validate_phone(v)

    @field_validator("description", "closed_message")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v else None

    @field_validator("opening_hours")
    @classmethod
    def _hours(cls, v: dict | None) -> dict | None:
        return normalize_opening_hours(v)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v: str | None) -> str | None:
        return validate_timezone(v) if v else v

    @field_validator("closed_until")
    @classmethod
    def _aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("closed_until must include a timezone (e.g. 2026-11-02T09:00:00+05:30)")
        return v

    @field_validator("slot_length_minutes")
    @classmethod
    def _slot_len(cls, v: int | None) -> int | None:
        if v is not None and v not in SLOT_LENGTHS:
            raise ValueError(f"Slot length must be one of {', '.join(map(str, SLOT_LENGTHS))} minutes")
        return v

    @field_validator("latitude")
    @classmethod
    def lat_in_range(cls, v: float | None) -> float | None:
        if v is not None and not -90 <= v <= 90:
            raise ValueError("latitude must be between -90 and 90")
        return v

    @field_validator("longitude")
    @classmethod
    def lng_in_range(cls, v: float | None) -> float | None:
        if v is not None and not -180 <= v <= 180:
            raise ValueError("longitude must be between -180 and 180")
        return v


    @field_validator("upi_id")
    @classmethod
    def valid_upi_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if v == "":
            return None
        if not is_valid_upi_id(v):
            raise ValueError("Enter a valid UPI ID, like shopname@okaxis")
        return normalize_upi_id(v)

    @field_validator("upi_qr_url")
    @classmethod
    def blank_qr_to_none(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v is not None else None


class ShopOut(BaseModel):
    """
    The PUBLIC shape — returned by GET /shops and GET /shops/{id}, which
    anyone (including a logged-out visitor) can call. Deliberately does
    NOT include approval_status, docs_status, documents, or
    rejection_reason: `documents` holds URLs to a seller's ID proof and
    business registration, which must never be reachable from a public,
    unauthenticated endpoint. See DashboardShopOut below for the
    owner/admin-facing shape that does include them.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    rating: float
    # Number of visible shop reviews behind `rating` (0 = no reviews yet).
    rating_count: int = 0
    is_active: bool
    created_at: datetime
    # Public — a storefront's rough location/address is meant to be
    # discoverable, same as any local business listing. All nullable
    # since shops created before migration 0009 have none on file.
    address_line1: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    # Public — a customer needs to know whether pickup is even offered
    # before checkout shows them the option. See Shop.pickup_enabled;
    # checkout additionally requires address_line1 to be set (nowhere to
    # pick up from otherwise), so a customer-facing "can I pick up here"
    # check should treat pickup_enabled AND address_line1 together, not
    # this field alone.
    pickup_enabled: bool = True
    # Public flags only (never the UPI id / QR themselves — those are
    # revealed per-order, see schemas/order.py's PaymentInfo). A shop
    # only really accepts UPI if accepts_upi is on AND it has a UPI id or
    # QR on file; the cart endpoint folds that into these two flags.
    accepts_upi: bool = True
    accepts_cash: bool = True
    # Only ever set by GET /shops when called with ?lat=&lng= (see
    # routers/shops.py) — a straight-line distance in km from the point
    # given, used to power "near me" search and sort. None on every other
    # call, including the plain unfiltered GET /shops.
    distance_km: float | None = None

    # ---- profile / hours / pricing / timing (all public) -----------------
    contact_phone: str | None = None
    description: str | None = None
    opening_hours: dict | None = None
    timezone: str = "Asia/Kolkata"
    # Computed at response time: {is_open, state, opens_at, closes_at, message}.
    # (Shop responses are cached for up to 60s — the checkout re-checks.)
    open_info: dict | None = None
    delivery_fee: Decimal = Decimal("0")
    free_delivery_above: Decimal | None = None
    min_order_amount: Decimal = Decimal("0")
    prep_time_minutes: int = 30
    delivery_time_minutes: int = 30
    slots_enabled: bool = False
    slot_length_minutes: int = 60
    slot_days_ahead: int = 2


class DashboardShopOut(ShopOut):
    """
    The OWNER-facing shape — GET/PUT /dashboard/shops only, always
    behind require_role("shop_owner", "admin") + an ownership check.
    Adds exactly the fields the Shop Dashboard needs to render "your
    application is pending/rejected/approved" and let the owner act on
    it (see ShopUpdate.documents above).
    """

    approval_status: str
    docs_status: str
    # Owner can see their own promotion status (never exposed publicly —
    # customers just see the resulting ranking).
    sponsored_until: datetime | None = None
    is_sponsored: bool = False
    documents: list[ShopDocument]
    rejection_reason: str | None
    attributes: dict
    # The owner's own payment details — see Shop.upi_id.
    upi_id: str | None = None
    upi_qr_url: str | None = None
    temporarily_closed: bool = False
    closed_until: datetime | None = None
    closed_message: str | None = None
    slot_capacity: int = 5
    low_stock_threshold: int = 5
    gstin: str | None = None
    legal_name: str | None = None
