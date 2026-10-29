"""
Pure helpers for how a product's price, size and identifiers are validated
and displayed. No database, so they're easy to test and reuse.

Terms
  * `price`  — the SELLING price: what the customer is charged (always).
  * `mrp`    — Maximum Retail Price printed on the pack. Optional; when set
               it must be >= price (selling above MRP is illegal for packaged
               goods in India), and the gap is shown as a discount.
  * unit     — pack size as a number + unit: 500 g, 1 L, 6 pcs.
"""
import re
from decimal import ROUND_HALF_UP, Decimal

# stored value -> how it's displayed
UNITS: dict[str, str] = {"g": "g", "kg": "kg", "ml": "ml", "l": "L", "pcs": "pcs", "pack": "pack", "dozen": "dozen"}
# weight/volume units -> (factor to the base unit, base unit)
_BASE = {"g": (Decimal(1), "g"), "kg": (Decimal(1000), "g"), "ml": (Decimal(1), "ml"), "l": (Decimal(1000), "ml")}

_SKU_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/ ]{0,39}$")
_CENT = Decimal("0.01")


def _plain(value: Decimal) -> str:
    """500.000 -> "500", 0.250 -> "0.25" (never scientific notation)."""
    text = f"{Decimal(str(value)).normalize():f}"
    return text


def unit_label(value, unit: str | None) -> str | None:
    """"500 g", "1 L", "6 pcs" — or None when no size is set."""
    if value is None or not unit or unit not in UNITS:
        return None
    return f"{_plain(Decimal(str(value)))} {UNITS[unit]}"


def discount_percent(mrp, price) -> int | None:
    """Whole-number percent off MRP, or None when there is no real discount
    (no MRP, MRP not above the price, or under half a percent)."""
    if mrp is None or price is None:
        return None
    mrp, price = Decimal(str(mrp)), Decimal(str(price))
    if mrp <= 0 or mrp <= price:
        return None
    pct = int(((mrp - price) / mrp * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return pct if pct >= 1 else None


def savings(mrp, price) -> Decimal:
    """Rupees saved per unit versus MRP (0 if none)."""
    if mrp is None or price is None:
        return Decimal("0.00")
    diff = Decimal(str(mrp)) - Decimal(str(price))
    return diff.quantize(_CENT) if diff > 0 else Decimal("0.00")


def unit_price_label(price, value, unit: str | None) -> str | None:
    """Comparison price for weight/volume packs: "₹8 / 100 g", "₹12.50 / 100 ml".
    Not shown for counts (pcs/pack/dozen) where it isn't meaningful."""
    if price is None or value is None or unit not in _BASE:
        return None
    factor, base = _BASE[unit]
    total = Decimal(str(value)) * factor
    if total <= 0:
        return None
    per_100 = (Decimal(str(price)) / total * 100).quantize(_CENT, rounding=ROUND_HALF_UP)
    amount = f"₹{per_100:f}".rstrip("0").rstrip(".") if per_100 == per_100.to_integral_value() else f"₹{per_100:f}"
    return f"{amount} / 100 {base}"


def clean_sku(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if not _SKU_RE.match(value):
        raise ValueError("SKU can use letters, numbers, spaces and . _ - / (up to 40 characters)")
    return value


def is_valid_gtin(code: str) -> bool:
    """EAN-8 / UPC-A (12) / EAN-13 / GTIN-14, including the check digit —
    which catches nearly every typo and bad scan."""
    if not code.isdigit() or len(code) not in (8, 12, 13, 14):
        return False
    digits = [int(c) for c in code]
    body, check = digits[:-1], digits[-1]
    total = sum(d * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def clean_barcode(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"[\s-]", "", value)
    if not value:
        return None
    if not is_valid_gtin(value):
        raise ValueError("That barcode isn't valid — check the digits (EAN-13, UPC-A or EAN-8, 8–14 digits).")
    return value
