"""
Bulk product upload from a CSV file — parsing and per-row validation (no
database; the router does the lookups and the writes).

Columns (header names are case-insensitive; spaces/dashes read as "_"):

  sku*            the key: a row whose SKU already exists in the shop UPDATES
                  that product, any other SKU creates a new one
  name            required to create
  price           required to create (selling price, EXCLUDING GST)
  category        required to create
  stock_qty, description, mrp, unit_value, unit, barcode,
  gst_rate, hsn_code, low_stock_threshold, is_active

On an UPDATE a blank cell means "leave as is" — never "erase". Images,
variants and category-specific attributes aren't part of the CSV; add them in
the product form afterwards.
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from app.core.product_pricing import clean_sku
from app.schemas.product import ProductCreate, ProductUpdate

MAX_ROWS = 2000

COLUMNS = (
    "sku", "name", "price", "category", "stock_qty", "description", "mrp",
    "unit_value", "unit", "barcode", "gst_rate", "hsn_code", "low_stock_threshold", "is_active",
)
_ALIASES = {
    "stock": "stock_qty", "quantity": "stock_qty", "qty": "stock_qty", "selling_price": "price",
    "gst": "gst_rate", "gst_%": "gst_rate", "hsn": "hsn_code", "pack_size": "unit_value",
    "active": "is_active", "low_stock_alert": "low_stock_threshold",
}
_DECIMAL_COLS = {"price", "mrp", "unit_value", "gst_rate"}
_INT_COLS = {"stock_qty", "low_stock_threshold"}
_TRUE, _FALSE = {"yes", "y", "true", "1", "active"}, {"no", "n", "false", "0", "inactive"}


class CsvError(ValueError):
    """The file as a whole is unusable (as opposed to a bad row)."""


def template_csv() -> str:
    rows = [
        COLUMNS,
        ("GHEE-1L", "Amul Ghee", "550", "Grocery", "40", "Pure cow ghee", "580", "1", "l", "", "12", "04059020", "5", "yes"),
        ("ATTA-5KG", "Aashirvaad Atta", "265", "Grocery", "25", "", "", "5", "kg", "", "0", "", "", "yes"),
    ]
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return out.getvalue()


def _norm_header(h: str) -> str:
    h = re.sub(r"[\s\-]+", "_", (h or "").strip().lower().lstrip("﻿"))
    return _ALIASES.get(h, h)


def parse_csv(text: str) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    """-> (columns present, [(line number, {column: cleaned string})]). Blank
    cells are dropped from each row's dict; fully blank lines are skipped."""
    text = text.lstrip("﻿")
    if not text.strip():
        raise CsvError("The file is empty.")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    try:
        header = [_norm_header(h) for h in next(reader)]
    except StopIteration:
        raise CsvError("The file is empty.") from None

    unknown = [h for h in header if h and h not in COLUMNS]
    if "sku" not in header:
        raise CsvError("The first row must be a header containing a 'sku' column. Download the template to start from.")
    if len(set(header)) != len(header):
        raise CsvError("Some column names appear twice in the header.")

    rows: list[tuple[int, dict[str, str]]] = []
    for line_no, raw in enumerate(reader, start=2):
        if not any(c.strip() for c in raw):
            continue
        rows.append((line_no, {h: c.strip() for h, c in zip(header, raw) if h in COLUMNS and c.strip()}))
        if len(rows) > MAX_ROWS:
            raise CsvError(f"Too many rows — upload at most {MAX_ROWS} products at a time.")
    if not rows:
        raise CsvError("The file has a header but no products.")
    return [h for h in header if h in COLUMNS] + [f"?{u}" for u in unknown], rows


def _convert(col: str, raw: str):
    if col in _DECIMAL_COLS:
        try:
            return Decimal(re.sub(r"(?i)(rs\.?|inr|₹|%|,)", "", raw).strip())
        except InvalidOperation:
            raise ValueError(f"{col}: '{raw}' is not a number") from None
    if col in _INT_COLS:
        try:
            d = Decimal(raw.replace(",", ""))
        except InvalidOperation:
            raise ValueError(f"{col}: '{raw}' is not a whole number") from None
        if d != d.to_integral_value():
            raise ValueError(f"{col}: '{raw}' must be a whole number")
        return int(d)
    if col == "is_active":
        v = raw.lower()
        if v in _TRUE:
            return True
        if v in _FALSE:
            return False
        raise ValueError("is_active: use yes or no")
    return raw


def _messages(exc: ValidationError) -> list[str]:
    out = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e["loc"])
        msg = e["msg"].removeprefix("Value error, ")
        out.append(msg if loc in ("", "__root__") or msg.lower().startswith(loc.split(".")[0]) else f"{loc}: {msg}")
    return out


def validate_row(raw: dict[str, str], *, shop_id: uuid.UUID, exists: bool) -> tuple[dict | None, list[str]]:
    """Validate one row. Returns (clean values to apply, error messages).
    `exists` = the SKU is already a product in this shop (update, not create)."""
    errors: list[str] = []
    values: dict = {}
    try:
        values["sku"] = clean_sku(raw.get("sku"))
    except ValueError as exc:
        return None, [str(exc)]
    if not values["sku"]:
        return None, ["sku is required — it's how each row is matched to a product"]
    for col, text in raw.items():
        if col == "sku":
            continue
        try:
            values[col] = _convert(col, text)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        return None, errors

    if not exists:
        missing = [c for c in ("name", "price", "category") if c not in values]
        if missing:
            return None, [f"New product (SKU not in your shop yet) is missing: {', '.join(missing)}"]
    body = {k: v for k, v in values.items() if k not in ("is_active",) and not (exists and k == "sku")}
    try:
        parsed = ProductUpdate(**body) if exists else ProductCreate(shop_id=shop_id, **body)
    except ValidationError as exc:
        return None, _messages(exc)
    # Normalised values (units lowercased, HSN spaces removed...) come from the schema.
    clean = parsed.model_dump(exclude_unset=True, exclude={"shop_id"})
    clean["sku"] = values["sku"]
    if "is_active" in values:
        clean["is_active"] = values["is_active"]
    return clean, []
