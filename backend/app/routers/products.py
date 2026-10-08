from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get_or_set
from app.core.db import get_db
from app.core.utils import parse_uuid_or_404
from app.models import PlatformSettings, Product, Shop
from app.schemas.product import ProductDetailOut, ProductOut, ProductSearchOut, VariantSummary
from app.routers.shops import DEFAULT_RADIUS_KM, _distance_expr
from app.schemas.shop import ShopOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{product_id}", response_model=ProductDetailOut)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    """
    Backs the Product Detail page. One cached call returns the product,
    its shop's info, AND its variant siblings (if any) together — the
    frontend needs all three to render the page (gallery + buy box +
    color/size picker), and this avoids multiple round trips.
    """
    pid = parse_uuid_or_404(product_id, "Product")

    async def load():
        result = await db.execute(
            select(Product).where(Product.id == pid, Product.is_active.is_(True))
        )
        product = result.scalar_one_or_none()
        if product is None:
            return None

        shop_result = await db.execute(select(Shop).where(Shop.id == product.shop_id))
        shop = shop_result.scalar_one_or_none()

        variants = []
        if product.variant_group_id is not None:
            siblings_result = await db.execute(
                select(Product).where(
                    Product.variant_group_id == product.variant_group_id, Product.is_active.is_(True)
                )
            )
            siblings = siblings_result.scalars().all()
            # A picker only makes sense with something to pick BETWEEN —
            # if every other variant in the group has since been
            # deactivated, this one is effectively standalone again.
            if len(siblings) > 1:
                variants = [
                    VariantSummary(
                        id=s.id,
                        variant_attributes=s.variant_attributes,
                        price=s.price,
                        stock_qty=s.stock_qty,
                        is_active=s.is_active,
                        thumbnail=s.images[0] if s.images else None,
                    ).model_dump(mode="json")
                    for s in siblings
                ]

        data = ProductOut.model_validate(product).model_dump(mode="json")
        data["shop"] = ShopOut.model_validate(shop).model_dump(mode="json") if shop else None
        data["variants"] = variants
        return data

    data = await cache_get_or_set(f"product:{product_id}", ttl_seconds=60, loader=load)
    if data is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return data


@router.get("", response_model=list[ProductSearchOut])
async def search_products(
    q: str | None = Query(default=None, description="Matched against product name/description"),
    category: str | None = Query(default=None),
    shop_id: str | None = Query(default=None, description="Restrict results to one shop's storefront"),
    lat: float | None = Query(default=None, description="Customer's latitude — limits results to nearby shops"),
    lng: float | None = Query(default=None, description="Customer's longitude — used together with lat"),
    radius_km: float | None = Query(
        default=None, gt=0, description="Defaults to the platform's max delivery radius setting"
    ),
    limit: int = Query(default=24, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Backs the Search page AND the public storefront page
    (`/store/[id]`, via `shop_id`) — deliberately NOT cached — search
    queries vary too much for cache-aside to pay off.

    RANKING (paid priority): results are ordered by
      1. in stock before out of stock — a paid slot is wasted on
         something the customer can't buy;
      2. products from a currently SPONSORED shop (Shop.sponsored_until
         in the future) before everyone else;
      3. name matches before description-only matches (only when `q`);
      4. nearer shops first when lat/lng were given, else higher-rated
         shops first; then newest.

    With `lat`+`lng`, results are limited to shops within `radius_km`
    (default: the platform's max delivery radius), so "sponsored first"
    applies among the shops that actually serve the customer's area — a
    shop across the city never outranks a local one just by paying.
    Sponsorship only changes the order — it is not exposed to customers.
    The customer still sees every matching product and picks freely.

    Only products from active + approved shops are returned (this also
    closes a gap where products of pending/rejected shops could surface
    in search results).

    Plain ILIKE matching is fine for a few thousand products; move to
    Postgres full-text search (tsvector + GIN) before reaching for a
    dedicated search engine.
    """
    sponsored = case((Shop.sponsored_until > func.now(), 1), else_=0)

    use_location = lat is not None and lng is not None
    distance = _distance_expr(lat, lng) if use_location else None
    distance_col = distance.label("distance_km") if use_location else None

    stmt = (
        select(
            Product,
            sponsored.label("sponsored"),
            Shop.name.label("shop_name"),
            *( [distance_col] if use_location else [] ),
        )
        .join(Shop, Shop.id == Product.shop_id)
        .where(
            Product.is_active.is_(True),
            Shop.is_active.is_(True),
            Shop.approval_status == "approved",
        )
    )

    if use_location:
        radius = radius_km
        if radius is None:
            settings_row = await db.get(PlatformSettings, 1)
            radius = float(settings_row.max_delivery_radius_km) if settings_row else DEFAULT_RADIUS_KM
        stmt = stmt.where(
            Shop.latitude.isnot(None), Shop.longitude.isnot(None), distance <= radius
        )

    if category:
        stmt = stmt.where(Product.category == category)

    if shop_id:
        sid = parse_uuid_or_404(shop_id, "Shop")
        stmt = stmt.where(Product.shop_id == sid)

    order = [
        case((Product.stock_qty > 0, 0), else_=1),
        sponsored.desc(),
    ]
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(pattern) | Product.description.ilike(pattern))
        order.append(case((Product.name.ilike(pattern), 0), else_=1))
    order += [distance.asc() if use_location else Shop.rating.desc(), Product.created_at.desc()]

    result = await db.execute(stmt.order_by(*order).limit(limit))
    out = []
    for row in result.all():
        item = ProductSearchOut.model_validate(row[0])
        item.shop_name = row[2]
        if use_location:
            item.distance_km = round(row[3], 2)
        out.append(item)
    return out
