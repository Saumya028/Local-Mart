import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AddressCreate(BaseModel):
    label: str
    line1: str
    city: str
    lat: float | None = None
    lng: float | None = None
    is_default: bool = False


class AddressUpdate(BaseModel):
    """All fields optional — this backs a PUT that can change just one
    field (e.g. only `is_default`) without the caller resending everything."""

    label: str | None = None
    line1: str | None = None
    city: str | None = None
    lat: float | None = None
    lng: float | None = None
    is_default: bool | None = None


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    line1: str
    city: str
    lat: float | None
    lng: float | None
    is_default: bool
    created_at: datetime
