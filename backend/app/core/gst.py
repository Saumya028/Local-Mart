"""
GST maths for invoices — pure functions, no database.

Prices in LocalMart EXCLUDE GST: the tax is added on top at checkout.

Per line:   tax = round(unit_price * qty * rate / 100, 2)
Split:      same-state supply  -> CGST + SGST (half each)
            different state    -> IGST (full)

Place of supply is decided from the first two digits of the two GSTINs
(the state code) when the buyer has given a GSTIN. Without a buyer GSTIN the
sale is treated as same-state: LocalMart is a hyperlocal marketplace, so the
buyer is overwhelmingly in the shop's own state.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# Slabs a product may carry (percent). 0 = exempt / nil-rated.
GST_RATES = (Decimal("0"), Decimal("0.25"), Decimal("3"), Decimal("5"), Decimal("12"), Decimal("18"), Decimal("28"))
_CENT = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP)


def line_tax(unit_price, qty: int, rate) -> Decimal:
    """GST on one order line (price excludes GST)."""
    return money(Decimal(str(unit_price)) * qty * Decimal(str(rate or 0)) / 100)


def state_code(gstin: str | None) -> str | None:
    if gstin and len(gstin) >= 2 and gstin[:2].isdigit():
        return gstin[:2]
    return None


def is_inter_state(shop_gstin: str | None, buyer_gstin: str | None) -> bool:
    a, b = state_code(shop_gstin), state_code(buyer_gstin)
    return a is not None and b is not None and a != b


@dataclass
class InvoiceLine:
    description: str
    hsn: str | None
    qty: int
    unit_price: Decimal
    rate: Decimal
    taxable: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal

    @property
    def tax(self) -> Decimal:
        return self.cgst + self.sgst + self.igst

    @property
    def total(self) -> Decimal:
        return self.taxable + self.tax


def build_line(description, hsn, qty, unit_price, rate, inter_state: bool) -> InvoiceLine:
    unit_price, rate = money(unit_price), Decimal(str(rate or 0))
    taxable = money(unit_price * qty)
    tax = line_tax(unit_price, qty, rate)
    if inter_state:
        cgst = sgst = Decimal("0.00")
        igst = tax
    else:
        cgst = money(tax / 2)
        sgst = tax - cgst
        igst = Decimal("0.00")
    return InvoiceLine(description, hsn, qty, unit_price, rate, taxable, cgst, sgst, igst)


_ONES = ("", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen")
_TENS = ("", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")


def _below_100(n: int) -> str:
    return _ONES[n] if n < 20 else (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else ""))


def _below_1000(n: int) -> str:
    out = []
    if n >= 100:
        out.append(_ONES[n // 100] + " Hundred")
        n %= 100
    if n:
        out.append(_below_100(n))
    return " ".join(out)


def amount_in_words(amount) -> str:
    """Indian numbering: 123456.50 -> "Rupees One Lakh Twenty Three Thousand Four Hundred Fifty Six and Fifty Paise Only"."""
    amount = money(amount)
    rupees, paise = int(amount), int((amount - int(amount)) * 100)
    parts = []
    for size, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
        if rupees >= size:
            parts.append(_below_100(rupees // size) + " " + name)
            rupees %= size
    if rupees:
        parts.append(_below_1000(rupees))
    words = " ".join(parts) or "Zero"
    text = f"Rupees {words}"
    if paise:
        text += f" and {_below_100(paise)} Paise"
    return text + " Only"


def financial_year(dt) -> str:
    """"2526" for 1 Apr 2025 – 31 Mar 2026 (the form used in invoice numbers)."""
    start = dt.year if dt.month >= 4 else dt.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"
