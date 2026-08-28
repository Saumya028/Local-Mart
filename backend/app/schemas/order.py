import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CheckoutRequest(BaseModel):
    delivery_address: str


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    shop_id: uuid.UUID
    status: str
    total_amount: Decimal
    delivery_address: str
    created_at: datetime


class CheckoutResponse(BaseModel):
    orders: list[OrderOut]
    client_secret: str | None
    total_amount: Decimal
