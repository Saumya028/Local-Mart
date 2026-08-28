from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get_or_set
from app.core.db import get_db
from app.core.utils import parse_uuid_or_404
from app.models import Product, Shop
from app.schemas.product import ProductDetailOut, ProductOut
from app.schemas.shop import ShopOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{product_id}", response_model=ProductDetailOut)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    """
    Backs the Product Detail page. One cached call returns the product
    AND its shop's info together — the frontend needs both to render the
    page, and this avoids the page making two separate round trips.
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

        data = ProductOut.model_validate(product).model_dump(mode="json")
        data["shop"] = ShopOut.model_validate(shop).model_dump(mode="json") if shop else None
        return data

    data = await cache_get_or_set(f"product:{product_id}", ttl_seconds=60, loader=load)
    if data is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return data


@router.get("", response_model=list[ProductOut])
async def search_products(
    q: str | None = Query(default=None, description="Matched against product name/description"),
    category: str | None = Query(default=None),
    limit: int = Query(default=24, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Backs the Search page. Deliberately NOT cached — search queries vary
    too much (different text, different filters) for cache-aside to pay
    off; almost every call would be a cache miss anyway.

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

    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(pattern) | Product.description.ilike(pattern))

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
