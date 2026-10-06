import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.core import customer_validation as cv


def _required(field: str, max_len: int):
    return lambda cls, v: cv.clean_text(v, field=field, max_len=max_len, required=True)


def _optional(field: str, max_len: int):
    return lambda cls, v: cv.clean_text(v, field=field, max_len=max_len)


class AddressCreate(BaseModel):
    """
    Amazon-style delivery address. recipient_name / phone / pincode / state
    are required for NEW addresses (the delivery partner needs them);
    older saved addresses without them still load fine — see the model.
    """

    label: str
    recipient_name: str
    phone: str
    line1: str
    line2: str | None = None
    landmark: str | None = None
    city: str
    state: str
    pincode: str
    lat: float | None = None
    lng: float | None = None
    is_default: bool = False

    _label = field_validator("label")(_required("Label", 30))
    _recipient = field_validator("recipient_name")(_required("Recipient name", 100))
    _line1 = field_validator("line1")(_required("Address line 1", 200))
    _line2 = field_validator("line2")(_optional("Address line 2", 200))
    _landmark = field_validator("landmark")(_optional("Landmark", 100))
    _city = field_validator("city")(_required("City", 80))

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        phone = cv.validate_phone(v)
        if phone is None:
            raise ValueError("Phone number is required")
        return phone

    @field_validator("state")
    @classmethod
    def _state(cls, v):
        state = cv.validate_state(v)
        if state is None:
            raise ValueError("State is required")
        return state

    @field_validator("pincode")
    @classmethod
    def _pincode(cls, v):
        pin = cv.validate_pincode(v)
        if pin is None:
            raise ValueError("PIN code is required")
        return pin


class AddressUpdate(BaseModel):
    """All fields optional — this backs a PUT that can change just one
    field (e.g. only `is_default`) without the caller resending everything."""

    label: str | None = None
    recipient_name: str | None = None
    phone: str | None = None
    line1: str | None = None
    line2: str | None = None
    landmark: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    lat: float | None = None
    lng: float | None = None
    is_default: bool | None = None

    _label = field_validator("label")(_optional("Label", 30))
    _recipient = field_validator("recipient_name")(_optional("Recipient name", 100))
    _line1 = field_validator("line1")(_optional("Address line 1", 200))
    _line2 = field_validator("line2")(_optional("Address line 2", 200))
    _landmark = field_validator("landmark")(_optional("Landmark", 100))
    _city = field_validator("city")(_optional("City", 80))
    _phone = field_validator("phone")(lambda cls, v: cv.validate_phone(v))
    _state = field_validator("state")(lambda cls, v: cv.validate_state(v))
    _pincode = field_validator("pincode")(lambda cls, v: cv.validate_pincode(v))


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    recipient_name: str | None = None
    phone: str | None = None
    line1: str
    line2: str | None = None
    landmark: str | None = None
    city: str
    state: str | None = None
    pincode: str | None = None
    lat: float | None
    lng: float | None
    is_default: bool
    created_at: datetime
