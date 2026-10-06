"""
Validation + normalisation for the customer details collected at signup /
My Account (DOB, gender, phone, GSTIN, PAN, address).

Kept as plain functions (no FastAPI/SQLAlchemy imports) so the same rules
are used by:
  - the Pydantic schemas (schemas/profile.py, schemas/address.py), which
    turn a ValueError into a 422 for the API caller, and
  - core/security.py's first-login provisioning, which reads the same
    fields out of the JWT's user_metadata and must NEVER crash a login
    over a bad value — it calls `safe()` so an invalid field is simply
    skipped (the customer can fill it in later under My Account).
"""
import re
from datetime import date

GENDERS = ("male", "female", "other", "prefer_not_to_say")
CUSTOMER_TYPES = ("individual", "business")

_GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_PINCODE_RE = re.compile(r"^[1-9][0-9]{5}$")
_GST_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# GST state codes (first two digits of a GSTIN) that are actually issued.
_VALID_GST_STATE_CODES = {f"{i:02d}" for i in range(1, 39)} | {"97", "99"}

INDIAN_STATES = (
    "Andaman and Nicobar Islands",
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chandigarh",
    "Chhattisgarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jammu and Kashmir",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Ladakh",
    "Lakshadweep",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Puducherry",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
)


def clean_text(value: str | None, *, field: str, max_len: int = 200, required: bool = False) -> str | None:
    """Trim + collapse whitespace. Empty string -> None (or an error if required)."""
    if value is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    value = " ".join(str(value).split())
    if not value:
        if required:
            raise ValueError(f"{field} is required")
        return None
    if len(value) > max_len:
        raise ValueError(f"{field} must be at most {max_len} characters")
    return value


def validate_full_name(value: str | None) -> str | None:
    name = clean_text(value, field="Full name", max_len=100)
    if name is not None and len(name) < 2:
        raise ValueError("Full name is too short")
    return name


def validate_phone(value: str | None) -> str | None:
    """
    Indian mobile numbers only: 10 digits starting 6-9, optionally written
    with +91 / 91 / 0 in front and spaces or dashes in between. Stored as
    "+91XXXXXXXXXX" so every row looks the same.
    """
    if value is None or not str(value).strip():
        return None
    digits = re.sub(r"[\s\-()]", "", str(value))
    if digits.startswith("+"):
        digits = digits[1:]
    if not digits.isdigit():
        raise ValueError("Enter a valid 10-digit mobile number")
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"[6-9][0-9]{9}", digits):
        raise ValueError("Enter a valid 10-digit mobile number")
    return f"+91{digits}"


def validate_dob(value: date | str | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            raise ValueError("Date of birth must be in YYYY-MM-DD format")
    today = date.today()
    if value > today:
        raise ValueError("Date of birth can't be in the future")
    if value.year < today.year - 120:
        raise ValueError("Enter a valid date of birth")
    return value


def validate_gender(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    value = str(value).strip().lower()
    if value not in GENDERS:
        raise ValueError(f"Gender must be one of: {', '.join(GENDERS)}")
    return value


def validate_customer_type(value: str | None) -> str | None:
    if value is None:
        return None
    value = str(value).strip().lower()
    if value not in CUSTOMER_TYPES:
        raise ValueError("Account type must be 'individual' or 'business'")
    return value


def validate_pan(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    value = str(value).strip().upper()
    if not _PAN_RE.fullmatch(value):
        raise ValueError("PAN must look like ABCDE1234F")
    return value


def _gstin_checksum_char(first_14: str) -> str:
    """Standard GSTN mod-36 check digit over the first 14 characters."""
    total = 0
    for i, ch in enumerate(first_14):
        product = _GST_CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += product // 36 + product % 36
    return _GST_CHARS[(36 - total % 36) % 36]


def validate_gstin(value: str | None) -> str | None:
    """
    Format + state code + check-digit validation. This proves the number is
    *well-formed*, NOT that it is registered or belongs to this customer —
    that needs the GST portal / a verification partner, which is why
    profiles.gst_verified exists and stays False until an admin confirms it.
    """
    if value is None or not str(value).strip():
        return None
    value = str(value).strip().upper()
    if not _GSTIN_RE.fullmatch(value) or value[:2] not in _VALID_GST_STATE_CODES:
        raise ValueError("GSTIN must be 15 characters, e.g. 27AAPFU0939F1ZV")
    if _gstin_checksum_char(value[:14]) != value[14]:
        raise ValueError("This GSTIN's check digit is wrong — please re-check it")
    return value


def validate_pincode(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    value = str(value).strip().replace(" ", "")
    if not _PINCODE_RE.fullmatch(value):
        raise ValueError("PIN code must be 6 digits")
    return value


def validate_state(value: str | None) -> str | None:
    state = clean_text(value, field="State", max_len=60)
    if state is None:
        return None
    for known in INDIAN_STATES:
        if known.lower() == state.lower():
            return known
    raise ValueError("Select a valid state / union territory")


def pan_from_gstin(gstin: str) -> str:
    """Characters 3-12 of a GSTIN are the holder's PAN."""
    return gstin[2:12]


def safe(fn, value):
    """Run a validator; on failure return None instead of raising."""
    try:
        return fn(value)
    except (ValueError, TypeError):
        return None
