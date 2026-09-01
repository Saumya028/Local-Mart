from decimal import Decimal

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_orders: int
    total_revenue: Decimal
    product_count: int
