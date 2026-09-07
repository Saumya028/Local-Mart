from decimal import Decimal

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_orders: int
    total_revenue: Decimal
    product_count: int


class DayPoint(BaseModel):
    """One point on a day-by-day chart — used for both the revenue trend
    line and the weekly order-count bars."""

    label: str  # e.g. "Mon"
    date: str  # ISO date, e.g. "2026-09-01"
    value: Decimal


class TopProductOut(BaseModel):
    id: str
    name: str
    units_sold: int
    revenue: Decimal


class RecentOrderPreview(BaseModel):
    id: str
    buyer_name: str | None
    buyer_email: str
    item_count: int
    total_amount: Decimal
    status: str
    created_at: str


class DashboardMetrics(BaseModel):
    """Feeds the Dashboard home tab: today's headline numbers, the
    7-day revenue chart, and a short top-products/recent-orders list."""

    today_revenue: Decimal
    today_orders: int
    yesterday_revenue: Decimal
    yesterday_orders: int
    pending_orders: int
    urgent_pending_orders: int
    avg_rating: float
    week_revenue_total: Decimal
    week_revenue_change_pct: float | None
    revenue_by_day: list[DayPoint]
    top_products: list[TopProductOut]
    recent_orders: list[RecentOrderPreview]


class AnalyticsOut(BaseModel):
    """Feeds the Analytics tab: all-time totals plus a couple of 7-day
    trend series."""

    total_revenue: Decimal
    total_orders: int
    unique_customers: int
    conversion_rate_pct: float
    orders_by_day: list[DayPoint]
    revenue_by_day: list[DayPoint]
