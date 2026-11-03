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

  images          file names of the product's pictures, separated by |
                  (e.g. oil-500.jpg|oil-500-back.jpg). The seller selects those
                  image files together with the CSV; the browser uploads them and
                  the API receives the resulting links in `image_map`. Every row
                  (including each variant) has its OWN images; blank = none (on
                  an update: blank = leave the product's images alone, filled =
                  REPLACE them). Links to other websites are not accepted.
  variant_group   the same name on every row that is a size/flavour of ONE product
                  (e.g. FORTUNE-OIL on the 500 ml row and the 1 l row). At least
                  two rows per group.
  variant_options what makes this row different, e.g. Size=500 ml  (several:
                  Size=500 ml|Colour=Red). Blank on a grouped row = labelled
                  "Size = <pack size>" automatically from unit_value + unit.

Each variant stays an ordinary product (own SKU, price, stock, images); the group
only links them so the product page can show a picker.

On an UPDATE a blank cell means "leave as is" — never "erase". Category-specific
attributes aren't part of the CSV; add them in the product form afterwards.
"""
from __future__ import annotations

import csv
import io
import re
import uuid
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from pydantic import ValidationError

from app.core.config import settings
from app.core.product_pricing import clean_sku, unit_label
from app.schemas.product import ProductCreate, ProductUpdate

MAX_ROWS = 2000
MAX_IMAGES_PER_PRODUCT = 8
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
IMAGES_BUCKET = "product-images"  # keep in sync with frontend/lib/imageUpload.ts

COLUMNS = (
    "sku", "name", "price", "category", "stock_qty", "description", "mrp",
    "unit_value", "unit", "barcode", "gst_rate", "hsn_code", "low_stock_threshold", "is_active",
    "images", "variant_group", "variant_options",
)
_ALIASES = {
    "stock": "stock_qty", "quantity": "stock_qty", "qty": "stock_qty", "selling_price": "price",
    "gst": "gst_rate", "gst_%": "gst_rate", "hsn": "hsn_code", "pack_size": "unit_value",
    "active": "is_active", "low_stock_alert": "low_stock_threshold",
    "image": "images", "image_files": "images", "image_names": "images", "photo": "images", "photos": "images",
    "group": "variant_group", "options": "variant_options", "variant_option": "variant_options",
}
_DECIMAL_COLS = {"price", "mrp", "unit_value", "gst_rate"}
_INT_COLS = {"stock_qty", "low_stock_threshold"}
_TRUE, _FALSE = {"yes", "y", "true", "1", "active"}, {"no", "n", "false", "0", "inactive"}


class CsvError(ValueError):
    """The file as a whole is unusable (as opposed to a bad row)."""


def template_csv() -> str:
    rows = [
        COLUMNS,
        ("GHEE-1L", "Amul Ghee", "550", "Grocery", "40", "Pure cow ghee", "580", "1", "l", "", "12", "04059020", "5", "yes",
         "ghee-1l.jpg", "", ""),
        ("ATTA-5KG", "Aashirvaad Atta", "265", "Grocery", "25", "", "", "5", "kg", "", "0", "", "", "yes",
         "atta-5kg.jpg|atta-5kg-back.jpg", "", ""),
        # One product, two sizes: same variant_group; the Size label is filled in from unit_value + unit.
        ("OIL-500ML", "Fortune Sunflower Oil", "95", "Grocery", "40", "Refined sunflower oil", "105", "500", "ml", "", "5",
         "15121910", "5", "yes", "oil-500ml.jpg|oil-500ml-back.jpg", "FORTUNE-OIL", ""),
        ("OIL-1L", "Fortune Sunflower Oil", "185", "Grocery", "25", "Refined sunflower oil", "205", "1", "l", "", "5",
         "15121910", "5", "yes", "oil-1l.jpg", "FORTUNE-OIL", ""),
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


def public_image_prefix() -> str | None:
    base = (settings.supabase_url or "").rstrip("/")
    return f"{base}/storage/v1/object/public/{IMAGES_BUCKET}/" if base else None


def is_own_image_url(url: str) -> bool:
    """True only for a public link inside OUR product-images bucket — so a CSV
    (or a forged request) can never point a product at some other website."""
    prefix = public_image_prefix()
    return bool(prefix) and url.startswith(prefix) and len(prefix) < len(url) <= 500 and ".." not in url


def parse_images(raw: str) -> list[str]:
    """"a.jpg|b.png" -> ["a.jpg", "b.png"] (path parts dropped, duplicates removed).
    Our own storage links pass through unchanged; any other link is refused."""
    out: list[str] = []
    seen: set[str] = set()
    for token in (t.strip() for t in re.split(r"[|;\n]+", raw)):
        if not token:
            continue
        if re.match(r"(?i)https?://", token):
            if not is_own_image_url(token):
                raise ValueError(
                    "images: links to other websites aren't supported — write the image file names "
                    "(e.g. oil.jpg) and select the files together with the CSV"
                )
            name = token
        else:
            name = re.split(r"[\\/]", token)[-1].strip()
            if not name.lower().endswith(IMAGE_EXTENSIONS) or len(name) > 150:
                raise ValueError(f"images: '{name}' isn't a .jpg, .png, .webp or .gif file name")
        if name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    if len(out) > MAX_IMAGES_PER_PRODUCT:
        raise ValueError(f"images: at most {MAX_IMAGES_PER_PRODUCT} pictures per product")
    return out


def parse_options(raw: str) -> dict[str, str]:
    """"Size=500 ml|Colour=Red" -> {"Size": "500 ml", "Colour": "Red"}."""
    out: dict[str, str] = {}
    for part in (p.strip() for p in re.split(r"[|;\n]+", raw)):
        if not part:
            continue
        m = re.match(r"^([^=:]+)[=:](.+)$", part)
        key, value = (m.group(1).strip(), m.group(2).strip()) if m else ("", "")
        if not key or not value or len(key) > 30 or len(value) > 60:
            raise ValueError("variant_options: write it like Size=500 ml (separate several with |)")
        if key.lower() in {k.lower() for k in out}:
            raise ValueError(f"variant_options: '{key}' appears twice")
        out[key] = value
    if len(out) > 3:
        raise ValueError("variant_options: at most 3 options per variant (e.g. Size and Colour)")
    return out


def resolve_images(tokens: list[str], image_map: dict[str, str], *, check_files: bool) -> tuple[list[str], list[str]]:
    """Turn a row's image tokens into stored links -> (links, problems).
    Own-bucket links pass through; file names are looked up (case-insensitively)
    in `image_map`, which the browser filled after uploading the files. With
    check_files=False (the dry run) names aren't looked up — nothing's uploaded yet."""
    urls: list[str] = []
    problems: list[str] = []
    for token in tokens:
        if token.lower().startswith(("http://", "https://")):
            urls.append(token)
        elif not check_files:
            continue
        elif token.lower() in image_map:
            urls.append(image_map[token.lower()])
        else:
            problems.append(f"images: '{token}' wasn't uploaded — select that file together with the CSV")
    return urls, problems


def _label(options: dict[str, str]) -> str:
    return ", ".join(f"{k} = {v}" for k, v in options.items())


def _signature(options: dict[str, str]) -> tuple:
    return tuple(sorted((k.lower(), v.lower()) for k, v in options.items()))


def plan_variants(
    entries: list[dict],
    group_sizes: dict[str, int],
    siblings: dict[uuid.UUID, list[dict]],
) -> tuple[dict[int, tuple[uuid.UUID, dict[str, str]]], dict[int, list[str]], list[dict]]:
    """
    Decide each row's variant group and options. Pure (no database).

    entries    one per valid row: line, sku, group (label or None), options
               (dict or None), unit_value, unit, existing_group_id, existing_options
    group_sizes   rows carrying each group label in the WHOLE file (valid or not),
               so one typo'd row is reported as the typo rather than hidden
    siblings   products already in a group but NOT being given a label in this file
               (group id -> [{sku, options}]) — new rows must be consistent with them

    Returns (line -> (group id, options), line -> problems, summary for the preview).
    """
    assign: dict[int, tuple[uuid.UUID, dict[str, str]]] = {}
    problems: dict[int, list[str]] = defaultdict(list)
    summary: list[dict] = []

    by_group: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        if e["group"]:
            by_group[e["group"].lower()].append(e)
        elif e["options"] is not None:
            if e["existing_group_id"] is None:
                problems[e["line"]].append(
                    "variant_options needs a variant_group — put the same name on every size/flavour of this product"
                )
            else:  # relabel a product that is already in a group
                assign[e["line"]] = (e["existing_group_id"], e["options"])

    for key, members in by_group.items():
        name = members[0]["group"]
        if group_sizes.get(key, 0) < 2:
            for m in members:
                problems[m["line"]].append(
                    f"variant_group '{name}' is on only one row — add the other sizes/flavours of this product "
                    "(or include one product that is already in the group), or leave variant_group blank"
                )
            continue
        existing_ids = {m["existing_group_id"] for m in members if m["existing_group_id"]}
        if len(existing_ids) > 1:
            for m in members:
                if m["existing_group_id"]:
                    problems[m["line"]].append(
                        f"variant_group '{name}' mixes products that already belong to different variant groups"
                    )
            continue
        gid = next(iter(existing_ids)) if existing_ids else uuid.uuid4()

        resolved: list[tuple[dict, dict[str, str]]] = []
        for m in members:
            options = m["options"]
            if options is None:
                options = m["existing_options"] or None
            if options is None:
                size = unit_label(m["unit_value"], m["unit"])
                if size is None:
                    problems[m["line"]].append(
                        "variant_options is blank and there's no pack size to label it from — write e.g. Size=500 ml, "
                        "or fill unit_value and unit"
                    )
                    continue
                options = {"Size": size}
            resolved.append((m, options))
        if not resolved:
            continue

        sibs = siblings.get(gid, [])
        reference = sibs[0]["options"] if sibs else resolved[0][1]
        ref_names = {k.lower(): k for k in reference}
        taken: dict[tuple, str] = {_signature(sb["options"]): sb["sku"] for sb in sibs}
        group_labels: list[str] = []
        for m, options in resolved:
            if {k.lower() for k in options} != set(ref_names):
                problems[m["line"]].append(
                    f"variant_options uses ({', '.join(options)}) but the rest of group '{name}' uses "
                    f"({', '.join(reference)}) — every variant in a group needs the same option names"
                )
                continue
            options = {ref_names[k.lower()]: v for k, v in options.items()}  # one spelling per group
            sig = _signature(options)
            if sig in taken:
                problems[m["line"]].append(
                    f"another variant in group '{name}' ({taken[sig]}) already has {_label(options)}"
                )
                continue
            taken[sig] = m["sku"]
            assign[m["line"]] = (gid, options)
            group_labels.append(_label(options))
        if group_labels:
            summary.append({"name": name, "rows": len(members), "options": group_labels})
    return assign, dict(problems), summary


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
    if col == "images":
        return parse_images(raw)
    if col == "variant_options":
        return parse_options(raw)
    if col == "variant_group":
        if len(raw) > 60:
            raise ValueError("variant_group: keep the name under 60 characters")
        return raw
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
    extras = {k: values.pop(k) for k in ("images", "variant_group", "variant_options") if k in values}
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
    # Not product columns — the router resolves these (images -> links, variant -> group).
    if "images" in extras:
        clean["_images"] = extras["images"]
    if "variant_group" in extras:
        clean["_group"] = extras["variant_group"]
    if "variant_options" in extras:
        clean["_options"] = extras["variant_options"]
    return clean, []
