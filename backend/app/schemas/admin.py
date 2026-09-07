import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

# The complete set of roles the platform understands. Kept as a plain
# tuple (not an enum wired into the DB) for the same reason
# scripts/promote_user.py does it this way — it's the single place that
# has to change if a role is ever added, and both the script and this
# router import it so they can never drift apart.
# "delivery_partner" added for the Manage Users page's "Delivery
# Partners" count — riders are just another profile role, not a
# separate identity table, since nothing else in the product yet needs
# more than "who is one".
VALID_ROLES = ("customer", "shop_owner", "admin", "delivery_partner")

# Every approval state a shop application can be in.
VALID_APPROVAL_STATUSES = ("pending", "approved", "rejected")
# Kept in sync by hand with app/schemas/shop.py's VALID_DOCS_STATUSES —
# "submitted" (owner uploaded, awaiting review) sits between "pending"
# (nothing on file / admin asked for more) and "verified" (admin signed
# off).
VALID_DOCS_STATUSES = ("pending", "submitted", "verified")


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    created_at: datetime
    is_suspended: bool
    orders_count: int = 0


class RoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f'"{v}" isn\'t a recognized role. Valid roles: {", ".join(VALID_ROLES)}')
        return v


class UserStatusUpdate(BaseModel):
    is_suspended: bool


class AdminShopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    rating: float
    is_active: bool
    approval_status: str
    docs_status: str
    documents: list[dict] = []
    rejection_reason: str | None = None
    created_at: datetime
    owner_id: uuid.UUID
    owner_email: str
    owner_name: str | None = None
    location: str | None = None


class RejectShopRequest(BaseModel):
    reason: str | None = None


class ShopStatusUpdate(BaseModel):
    is_active: bool


class AuditLogOut(BaseModel):
    id: uuid.UUID
    admin_email: str | None
    action: str
    target_type: str
    target_id: uuid.UUID | None
    details: dict
    created_at: datetime


class PlatformMetrics(BaseModel):
    """
    Backs the roadmap's "basic platform metrics (GMV, order count, active
    shops)" line item. GMV (Gross Merchandise Value) here means the sum
    of `total_amount` across CONFIRMED orders only — same rule the Shop
    Dashboard's own summary endpoint already uses for revenue, so the
    two numbers are consistent with each other rather than counting
    unpaid/failed orders as "sales" in one place and not the other.
    """

    total_users: int
    total_shop_owners: int
    total_admins: int
    total_shops: int
    active_shops: int
    total_products: int
    active_products: int
    total_orders: int
    confirmed_orders: int
    gmv: Decimal


class DashboardSummary(BaseModel):
    """The four top cards on the Admin Panel's Dashboard tab."""

    total_shops: int
    shops_added_this_month: int
    total_users: int
    users_added_this_week: int
    monthly_orders: int
    monthly_orders_change_pct: float | None
    platform_revenue: Decimal
    platform_revenue_change_pct: float | None


class UsersSummary(BaseModel):
    """The three top cards on the Admin Panel's Manage Users tab."""

    total_customers: int
    shop_owners: int
    delivery_partners: int


class MonthPoint(BaseModel):
    """One bar/line-chart point: a calendar month label + a value."""

    label: str
    value: Decimal


class CategoryShare(BaseModel):
    """One slice of the category donut/pie charts (orders or revenue %)."""

    category: str
    pct: float


class PaymentGateway(BaseModel):
    key: str
    name: str
    enabled: bool
    primary: bool


class PlatformSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    commission_pct: Decimal
    delivery_payout: Decimal
    min_order_amount: Decimal
    max_delivery_radius_km: Decimal
    payment_gateways: list[PaymentGateway]
    updated_at: datetime


class PlatformSettingsUpdate(BaseModel):
    """
    Every field optional — the Settings page edits one card/one gateway
    toggle at a time (matching the mockup's per-row "Edit" buttons), never
    the whole settings object at once, so a partial PATCH-style update
    (sent via PUT for simplicity) shouldn't require resending fields the
    admin didn't touch.
    """

    commission_pct: Decimal | None = None
    delivery_payout: Decimal | None = None
    min_order_amount: Decimal | None = None
    max_delivery_radius_km: Decimal | None = None
    payment_gateways: list[PaymentGateway] | None = None
