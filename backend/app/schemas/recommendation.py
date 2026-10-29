import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Surface = Literal["product", "cart", "home", "buy_again"]


class RecoItem(BaseModel):
    """One recommended product, shaped like a search-result card plus a
    human-readable `reason` ("Customers who bought Rice also bought this")."""

    id: uuid.UUID
    shop_id: uuid.UUID
    name: str
    price: Decimal
    mrp: Decimal | None = None
    unit_label: str | None = None
    discount_percent: int | None = None
    category: str
    stock_qty: int
    images: list = []
    rating_avg: float = 0.0
    rating_count: int = 0
    shop_name: str | None = None
    distance_km: float | None = None
    reason: str | None = None


class RecoResponse(BaseModel):
    surface: Surface
    # Echoed back by the frontend with each impression/click so results can be
    # attributed to the model build and the experiment arm that produced them.
    run_id: uuid.UUID | None = None
    variant: Literal["model", "baseline", "holdout"] = "model"
    items: list[RecoItem] = []


class RecoEventIn(BaseModel):
    surface: str
    event: str
    product_id: uuid.UUID
    position: int | None = Field(default=None, ge=0, le=100)
    run_id: uuid.UUID | None = None
    variant: str = "model"


class RecoEventsRequest(BaseModel):
    events: list[RecoEventIn] = Field(max_length=50)


class RecoEventsResponse(BaseModel):
    recorded: int


# ---- Admin -----------------------------------------------------------------


class RecoRunOut(BaseModel):
    id: uuid.UUID
    status: str
    is_active: bool
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None
    error: str | None = None
    stats: dict = {}


class RecoStatusOut(BaseModel):
    enabled: bool
    holdout_pct: int
    min_co_buyers: int
    excluded_categories: list[str]
    # ok | stale | no_model | disabled
    health: str
    active_run: RecoRunOut | None = None
    age_hours: float | None = None
    stale_after_hours: int
    recent_runs: list[RecoRunOut] = []


class RecoMetricRow(BaseModel):
    surface: str
    variant: str
    impressions: int
    clicks: int
    add_to_carts: int
    ctr: float
    add_to_cart_rate: float
    orders: int
    revenue: Decimal
    revenue_per_1000_impressions: float


class RecoMetricsOut(BaseModel):
    days: int
    rows: list[RecoMetricRow]


class RecoHealthOut(BaseModel):
    status: str  # ok | stale | no_model | disabled
    age_hours: float | None = None
    run_id: uuid.UUID | None = None

