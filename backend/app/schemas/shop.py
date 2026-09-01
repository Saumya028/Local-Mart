import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ShopCreate(BaseModel):
    name: str
    category: str


class ShopUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    is_active: bool | None = None


class ShopOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    rating: float
    is_active: bool
    created_at: datetime
