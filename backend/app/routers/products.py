from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get_or_set
from app.core.db import get_db
from app.core.utils import parse_uuid_or_404
from app.models import Product, Shop
from app.schemas.product import ProductDetailOut, ProductOut, VariantSummary
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


@router.get("", response_model=list[ProductOut])
async def search_products(
    q: str | None = Query(default=None, description="Matched against product name/description"),
    category: str | None = Query(default=None),
    shop_id: str | None = Query(default=None, description="Restrict results to one shop's storefront"),
    limit: int = Query(default=24, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Backs the Search page AND the public storefront page
    (`/store/[id]`, via `shop_id`) — deliberately NOT cached — search
    queries vary too much (different text, different filters) for
    cache-aside to pay off; almost every call would be a cache miss
    anyway.

    We're using a plain case-insensitive substring match (ILIKE) here,
    which is genuinely fine for a catalog of a few thousand products. If
    the catalog grows into the tens of thousands and this gets slow, the
    right next step is Postgres full-text search (`tsvector` + a GIN
    index) — and only after that, a dedicated search engine like
    OpenSearch. Don't reach for either before you actually need it.
    """
    stmt = select(Product).where(Product.is_active.is_(True))

    if category:
        stmt = stmt.where(Product.category == category)

    if shop_id:
        sid = parse_uuid_or_404(shop_id, "Shop")
        # Joined against Shop's own public-visibility rule (same as
        # GET /shops/{id} above) — a pending/rejected/deactivated shop's
        # products must stay invisible here too, not just off its own
        # page, or its catalog would still leak through this filter.
        stmt = stmt.join(Shop, Shop.id == Product.shop_id).where(
            Product.shop_id == sid, Shop.is_active.is_(True), Shop.approval_status == "approved"
        )

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(pattern) | Product.description.ilike(pattern))

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
