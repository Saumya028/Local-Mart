import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

# The complete set of roles the platform understands. Kept as a plain
# tuple (not an enum wired into the DB) for the same reason
# scripts/promote_user.py does it this way — it's the single place that
# has to change if a role is ever added, and both the script and this
# router import it so they can never drift apart.
VALID_ROLES = ("customer", "shop_owner", "admin")


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None
    role: str
    created_at: datetime


class RoleUpdate(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f'"{v}" isn\'t a recognized role. Valid roles: {", ".join(VALID_ROLES)}')
        return v


class AdminShopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    rating: float
    is_active: bool
    created_at: datetime
    owner_id: uuid.UUID
    owner_email: str


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
