"""
Helpers for direct UPI payments (customer -> shop, never through the
platform).

The platform can't see whether a UPI transfer happened, so everything
here is about (a) validating what a shop owner / customer types in and
(b) building the `upi://pay` deep link that opens the customer's UPI app
with payee, amount and a note pre-filled.
"""
import re
from decimal import Decimal
from urllib.parse import quote

# Virtual payment address: <handle>@<psp>, e.g. "shopname@okaxis",
# "9876543210@ybl". Handle allows letters, digits, dot, dash, underscore;
# PSP handle is letters only. Matches what NPCI-issued VPAs look like.
UPI_ID_RE = re.compile(r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$")

# UTR / UPI reference numbers are 12 digits for UPI; banks sometimes
# show longer alphanumeric transaction ids, so accept 8-30 alphanumerics.
PAYER_REF_RE = re.compile(r"^[A-Za-z0-9]{8,30}$")

PAYMENT_METHODS = ("upi", "cash")


def is_valid_upi_id(value: str) -> bool:
    return bool(UPI_ID_RE.match(value.strip()))


def normalize_upi_id(value: str) -> str:
    return value.strip().lower()


def is_valid_payer_reference(value: str) -> bool:
    return bool(PAYER_REF_RE.match(value.strip()))


def build_upi_link(upi_id: str, payee_name: str, amount: Decimal, note: str) -> str:
    """`upi://pay?pa=...&pn=...&am=...&cu=INR&tn=...` — opens GPay/PhonePe/
    Paytm/BHIM on a phone. Amount is fixed to two decimals."""
    amount_str = f"{Decimal(amount):.2f}"
    return (
        f"upi://pay?pa={quote(upi_id, safe='@')}"
        f"&pn={quote(payee_name)}"
        f"&am={amount_str}"
        f"&cu=INR"
        f"&tn={quote(note)}"
    )
