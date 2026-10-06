import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.core import customer_validation as cv


class ProfileOut(BaseModel):
    """
    What we send back to the frontend for a profile. Separate from the
    SQLAlchemy model on purpose — the API's shape shouldn't be forced to
    match the database's shape 1:1 forever (e.g. we'd never want to
    accidentally expose an internal-only column just because it exists
    on the model).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str | None
    full_name: str | None
    phone: str | None
    role: str
    created_at: datetime
    # Only ever set for a staff account (role="manager"/"delivery_partner") —
    # see models/profile.py. The frontend uses this so a staff member's
    # dashboard knows which shop to load without a separate lookup.
    shop_id: uuid.UUID | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    customer_type: str = "individual"
    business_name: str | None = None
    gstin: str | None = None
    pan: str | None = None
    # Read-only for the customer: set by an admin/verification step only.
    gst_verified: bool = False


class ProfileUpdate(BaseModel):
    """
    My Account > Settings. Deliberately does NOT include `email` or
    `role` — email changes go through Supabase Auth (which owns login
    identity, not this table), and role changes are an admin action
    (see routers/admin.py's update_user_role), never something a user
    sets on themselves.
    """

    full_name: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    customer_type: str | None = None
    business_name: str | None = None
    gstin: str | None = None
    pan: str | None = None

    # `gst_verified` is deliberately absent — see Profile.gst_verified.

    _full_name = field_validator("full_name")(lambda cls, v: cv.validate_full_name(v))
    _phone = field_validator("phone")(lambda cls, v: cv.validate_phone(v))
    _dob = field_validator("date_of_birth")(lambda cls, v: cv.validate_dob(v))
    _gender = field_validator("gender")(lambda cls, v: cv.validate_gender(v))
    _type = field_validator("customer_type")(lambda cls, v: cv.validate_customer_type(v))
    _biz = field_validator("business_name")(
        lambda cls, v: cv.clean_text(v, field="Business name", max_len=150)
    )
    _gstin = field_validator("gstin")(lambda cls, v: cv.validate_gstin(v))
    _pan = field_validator("pan")(lambda cls, v: cv.validate_pan(v))
