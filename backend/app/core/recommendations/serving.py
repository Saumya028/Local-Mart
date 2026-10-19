"""
ONLINE serving: what the API does per request. Everything here is a handful
of indexed lookups against the tables the nightly build wrote — no model is
loaded and nothing is computed over the whole catalogue.

Every shelf is built the same way:
  1. candidates   from the ACTIVE run's product_similarity rows;
  2. eligibility  only products a customer can actually buy right now
                  (active, in stock, from an open + approved shop, inside the
                  delivery radius, not in an excluded category);
  3. ranking      scoring.rank_candidates (the same function the offline
                  evaluator scores), then scoring.apply_diversity;
  4. fallback     top up with similar-category / trending products, so a shelf
                  is never empty just because the model knows little yet.
Personal (home) shelves use the customer's own history; product and cart
shelves use only the product / cart contents, so they work for anyone.
"""
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, null, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache_get_or_set
from app.core.config import settings
from app.core.order_status import RECOGNIZED_STATUSES
from app.core.recommendations import scoring
from app.models import (
    Order,
    OrderItem,
    PlatformSettings,
    Product,
    ProductPopularity,
    ProductReview,
    ProductSimilarity,
    Profile,
    RecommendationRun,
    ReturnRequest,
    Shop,
    WishlistItem,
)
from app.schemas.recommendation import RecoItem

HISTORY_ITEMS = 20  # same cap the offline evaluator uses
MAX_PER_SHOP = 3
MAX_PER_CATEGORY = 4
DEFAULT_RADIUS_KM = 5.0
STATEMENT_TIMEOUT_MS = 2000
BUY_AGAIN_HALF_LIFE_DAYS = 60
CACHE_TTL_SECONDS = 120


@dataclass(frozen=True)
class Viewer:
    """Where the shopper is. Without a location, no distance filter applies."""

    lat: float | None = None
    lng: float | None = None
    radius_km: float | None = None

    @property
    def located(self) -> bool:
        return self.lat is not None and self.lng is not None


# --------------------------------------------------------------------------
# Plumbing
# --------------------------------------------------------------------------


async def start_request(db: AsyncSession) -> None:
    """A recommendation is a nice-to-have: never let one slow query hold a
    connection (or a page) hostage."""
    await db.execute(text(f"SET LOCAL statement_timeout = {STATEMENT_TIMEOUT_MS}"))


async def active_run_id(db: AsyncSession) -> uuid.UUID | None:
    async def load():
        rid = (
            await db.execute(select(RecommendationRun.id).where(RecommendationRun.is_active.is_(True)))
        ).scalar_one_or_none()
        return str(rid) if rid else None

    value = await cache_get_or_set(scoring.ACTIVE_RUN_CACHE_KEY, 60, load)
    return uuid.UUID(value) if value else None


async def resolve_viewer(db: AsyncSession, lat: float | None, lng: float | None, radius_km: float | None) -> Viewer:
    if lat is None or lng is None:
        return Viewer()
    radius = radius_km
    if radius is None:
        row = await db.get(PlatformSettings, 1)
        radius = float(row.max_delivery_radius_km) if row else DEFAULT_RADIUS_KM
    return Viewer(lat, lng, radius)


def _excluded() -> list[str]:
    return settings.reco_excluded_category_list


def _item(product: Product, shop_name: str | None, distance: float | None, reason: str | None) -> dict:
    return RecoItem(
        id=product.id,
        shop_id=product.shop_id,
        name=product.name,
        price=product.price,
        category=product.category,
        stock_qty=product.stock_qty,
        images=product.images or [],
        rating_avg=product.rating_avg or 0.0,
        rating_count=product.rating_count or 0,
        shop_name=shop_name,
        distance_km=round(distance, 2) if distance is not None else None,
        reason=reason,
    ).model_dump(mode="json")


def _eligible_stmt(viewer: Viewer, *, apply_excluded: bool = True, extra_columns=()):
    # imported here: routers.shops is the single home of the haversine SQL
    from app.routers.shops import _distance_expr

    distance = _distance_expr(viewer.lat, viewer.lng) if viewer.located else None
    cols = [Product, Shop.name, (distance if distance is not None else null()).label("distance_km"), *extra_columns]
    stmt = (
        select(*cols)
        .join(Shop, Shop.id == Product.shop_id)
        .where(
            Product.is_active.is_(True),
            Product.stock_qty > 0,
            Shop.is_active.is_(True),
            Shop.approval_status == "approved",
        )
    )
    if viewer.located:
        stmt = stmt.where(
            Shop.latitude.isnot(None), Shop.longitude.isnot(None), distance <= (viewer.radius_km or DEFAULT_RADIUS_KM)
        )
    if apply_excluded and _excluded():
        stmt = stmt.where(Product.category.notin_(_excluded()))
    return stmt


async def load_eligible(
    db: AsyncSession, ids: set[str], viewer: Viewer, *, apply_excluded: bool = True
) -> dict[str, tuple[Product, str | None, float | None]]:
    """product id -> (product, shop name, distance km) for those of `ids`
    that a customer at `viewer` could actually buy right now."""
    if not ids:
        return {}
    stmt = _eligible_stmt(viewer, apply_excluded=apply_excluded).where(Product.id.in_([uuid.UUID(i) for i in ids]))
    return {str(p.id): (p, shop, dist) for p, shop, dist in (await db.execute(stmt)).all()}


async def _names(db: AsyncSession, ids: set[str]) -> dict[str, str]:
    if not ids:
        return {}
    rows = await db.execute(select(Product.id, Product.name).where(Product.id.in_([uuid.UUID(i) for i in ids])))
    return {str(i): n for i, n in rows.all()}


# --------------------------------------------------------------------------
# Candidate generation + ranking
# --------------------------------------------------------------------------


async def _model_shelf(
    db: AsyncSession,
    run_id: uuid.UUID | None,
    history: dict[str, float],
    *,
    kinds: tuple[str, ...],
    exclude: set[str],
    viewer: Viewer,
    limit: int,
) -> list[tuple[Product, str | None, float | None, str]]:
    """Collaborative-filtering shelf: [(product, shop, distance, because_product_id)]."""
    if run_id is None or not history:
        return []
    sims: dict[str, dict[str, float]] = defaultdict(dict)  # source -> candidate -> best sim over kinds
    for kind in kinds:
        rows = await db.execute(
            select(ProductSimilarity.product_id, ProductSimilarity.similar_product_id, ProductSimilarity.score).where(
                ProductSimilarity.run_id == run_id,
                ProductSimilarity.kind == kind,
                ProductSimilarity.product_id.in_([uuid.UUID(p) for p in history]),
            )
        )
        for src, cand, score in rows.all():
            s, c = str(src), str(cand)
            sims[s][c] = max(sims[s].get(c, 0.0), score)
    candidates = {c for per in sims.values() for c in per} - exclude
    if not candidates:
        return []

    eligible = await load_eligible(db, candidates, viewer)
    if not eligible:
        return []
    pop_rows = await db.execute(
        select(ProductPopularity.product_id, ProductPopularity.score).where(
            ProductPopularity.run_id == run_id, ProductPopularity.product_id.in_([uuid.UUID(c) for c in eligible])
        )
    )
    pop = {str(p): s for p, s in pop_rows.all()}
    neighbors = {
        src: [(c, s, pop.get(c, 0.0)) for c, s in per.items() if c in eligible] for src, per in sims.items()
    }
    ranked = scoring.rank_candidates(history, neighbors, exclude=exclude, limit=limit * 4)
    shaped = scoring.apply_diversity(
        ranked,
        {c: str(eligible[c][0].shop_id) for c, *_ in ranked},
        {c: eligible[c][0].category for c, *_ in ranked},
        max_per_shop=MAX_PER_SHOP,
        max_per_category=MAX_PER_CATEGORY,
        limit=limit,
    )
    return [(eligible[c][0], eligible[c][1], eligible[c][2], because) for c, _score, because in shaped]


async def _trending(
    db: AsyncSession,
    run_id: uuid.UUID | None,
    viewer: Viewer,
    *,
    exclude: set[str],
    limit: int,
    category: str | None = None,
) -> list[tuple[Product, str | None, float | None]]:
    """Most-bought eligible products (recency-weighted distinct buyers from the
    active run), best-reviewed / newest as the tie-break — which is also the
    whole ranking until the first model run exists."""
    pop_score = func.coalesce(ProductPopularity.score, 0.0)
    stmt = _eligible_stmt(viewer)
    if run_id is not None:
        stmt = stmt.outerjoin(
            ProductPopularity, (ProductPopularity.product_id == Product.id) & (ProductPopularity.run_id == run_id)
        )
        order = [pop_score.desc()]
    else:
        order = []
    if exclude:
        stmt = stmt.where(Product.id.notin_([uuid.UUID(e) for e in exclude]))
    if category:
        stmt = stmt.where(Product.category == category)
    stmt = stmt.order_by(*order, Product.rating_count.desc(), Product.rating_avg.desc(), Product.created_at.desc()).limit(
        limit * 4
    )
    rows = (await db.execute(stmt)).all()
    picked = scoring.apply_diversity(
        [(str(p.id), 0.0, "") for p, *_ in rows],
        {str(p.id): str(p.shop_id) for p, *_ in rows},
        {str(p.id): p.category for p, *_ in rows},
        max_per_shop=MAX_PER_SHOP,
        max_per_category=MAX_PER_CATEGORY,
        limit=limit,
    )
    by_id = {str(p.id): (p, shop, dist) for p, shop, dist, *_ in rows}
    return [by_id[pid] for pid, *_ in picked]


def _trending_reason(viewer: Viewer) -> str:
    return "Trending near you" if viewer.located else "Popular on LocalMart"


# --------------------------------------------------------------------------
# The four shelves
# --------------------------------------------------------------------------


async def recommend_for_product(db: AsyncSession, product_id: uuid.UUID, viewer: Viewer, limit: int) -> tuple[list[dict], uuid.UUID | None]:
    """"Customers also bought" on a product page. Uses only this product, so
    it is the same for everyone (and cached)."""
    run_id = await active_run_id(db)

    async def load():
        source = (await db.execute(select(Product).where(Product.id == product_id))).scalar_one_or_none()
        if source is None or source.category in _excluded():
            return []
        pid = str(product_id)
        model = await _model_shelf(
            db, run_id, {pid: 1.0}, kinds=("also_bought",), exclude={pid}, viewer=viewer, limit=limit
        )
        items = [
            _item(p, shop, dist, f"Customers who bought {source.name} also bought this") for p, shop, dist, _b in model
        ]
        seen = {pid} | {i["id"] for i in items}
        if len(items) < limit:
            for p, shop, dist in await _trending(
                db, run_id, viewer, exclude=seen, limit=limit - len(items), category=source.category
            ):
                items.append(_item(p, shop, dist, "Similar items"))
        return items

    key = f"reco:product:{product_id}:{scoring.geo_bucket(viewer.lat, viewer.lng)}:{run_id}:{limit}"
    return await cache_get_or_set(key, CACHE_TTL_SECONDS, load), run_id


async def recommend_for_cart(db: AsyncSession, cart: dict[str, int], viewer: Viewer, limit: int) -> tuple[list[dict], uuid.UUID | None]:
    """"Frequently bought together" for what is in the cart right now."""
    run_id = await active_run_id(db)
    if not cart:
        return [], run_id
    in_cart = set(cart)
    names = await _names(db, in_cart)
    # items in excluded categories never seed a cross-customer recommendation
    safe_rows = await db.execute(
        select(Product.id).where(Product.id.in_([uuid.UUID(i) for i in in_cart]), Product.category.notin_(_excluded()))
    )
    safe = {str(i) for i in safe_rows.scalars().all()}
    history = {p: 1.0 for p in safe}
    model = await _model_shelf(
        db, run_id, history, kinds=("bought_together", "also_bought"), exclude=in_cart, viewer=viewer, limit=limit
    )
    items = [
        _item(p, shop, dist, f"Often bought with {names.get(because, 'items in your cart')}")
        for p, shop, dist, because in model
    ]
    return items, run_id


async def _user_history(db: AsyncSession, user: Profile):
    """The customer's own affinities, computed with the SAME function the
    nightly build uses (so personal shelves match what was evaluated)."""
    returned = (
        select(ReturnRequest.order_item_id, func.sum(ReturnRequest.quantity).label("qty"))
        .where(ReturnRequest.status == "completed")
        .group_by(ReturnRequest.order_item_id)
        .subquery()
    )
    excluded = _excluded()
    purchases = [
        tuple(r)
        for r in (
            await db.execute(
                select(Order.user_id, OrderItem.product_id, Order.status, func.coalesce(Order.delivered_at, Order.created_at), Order.id)
                .select_from(OrderItem)
                .join(Order, Order.id == OrderItem.order_id)
                .join(Product, Product.id == OrderItem.product_id)
                .outerjoin(returned, returned.c.order_item_id == OrderItem.id)
                .where(
                    Order.user_id == user.id,
                    Order.status.in_(RECOGNIZED_STATUSES),
                    func.coalesce(returned.c.qty, 0) < OrderItem.quantity,
                    Product.category.notin_(excluded),
                )
            )
        ).all()
    ]
    wishlist = [
        tuple(r)
        for r in (
            await db.execute(
                select(WishlistItem.user_id, WishlistItem.product_id, WishlistItem.created_at)
                .join(Product, Product.id == WishlistItem.product_id)
                .where(WishlistItem.user_id == user.id, Product.category.notin_(excluded))
            )
        ).all()
    ]
    reviews = [
        tuple(r)
        for r in (
            await db.execute(
                select(ProductReview.user_id, ProductReview.product_id, ProductReview.rating).where(
                    ProductReview.user_id == user.id, ProductReview.is_hidden.is_(False)
                )
            )
        ).all()
    ]
    data = scoring.interaction_weights(
        purchases, wishlist, reviews, now=datetime.now(timezone.utc), half_life_days=settings.reco_half_life_days
    )
    weights = {p: w for (_u, p), w in data.weights.items()}
    purchased = {p for (_u, p) in data.purchase_weights}
    return weights, purchased


async def recommend_for_home(
    db: AsyncSession, user: Profile | None, viewer: Viewer, limit: int
) -> tuple[list[dict], uuid.UUID | None, str]:
    """
    "Recommended for you" (personal) or "Trending near you" (everyone else).
    Returns (items, run_id, variant). variant is the experiment arm:
    "model" (got personalised results), "holdout" (control group, deliberately
    shown the baseline) or "baseline" (anonymous / opted out / no history).
    """
    run_id = await active_run_id(db)
    in_control = user is not None and scoring.in_holdout(str(user.id), settings.reco_holdout_pct)
    personal = user is not None and not user.personalization_opt_out and not in_control and run_id is not None

    items: list[dict] = []
    owned: set[str] = set()
    if personal:
        weights, purchased = await _user_history(db, user)
        owned = set(weights)
        history = dict(sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))[:HISTORY_ITEMS])
        names = await _names(db, set(history))
        model = await _model_shelf(
            db, run_id, history, kinds=("also_bought",), exclude=owned, viewer=viewer, limit=limit
        )
        for p, shop, dist, because in model:
            verb = "bought" if because in purchased else "saved"
            items.append(_item(p, shop, dist, f"Because you {verb} {names.get(because, 'this')}"))

    personalised = bool(items)
    if len(items) < limit:
        seen = owned | {i["id"] for i in items}
        for p, shop, dist in await _trending(db, run_id, viewer, exclude=seen, limit=limit - len(items)):
            items.append(_item(p, shop, dist, _trending_reason(viewer)))

    variant = "holdout" if in_control else ("model" if personalised else "baseline")
    return items, run_id, variant


async def buy_again(db: AsyncSession, user: Profile, viewer: Viewer, limit: int) -> list[dict]:
    """Things this customer already bought, most likely to be re-bought
    first (how often, how recently) — from their OWN orders, so it needs no
    model, works for opted-out customers and may include any category."""
    rows = (
        await db.execute(
            select(
                OrderItem.product_id,
                func.count(func.distinct(Order.id)),
                func.max(func.coalesce(Order.delivered_at, Order.created_at)),
            )
            .select_from(OrderItem)
            .join(Order, Order.id == OrderItem.order_id)
            .where(Order.user_id == user.id, Order.status.in_(RECOGNIZED_STATUSES))
            .group_by(OrderItem.product_id)
        )
    ).all()
    now = datetime.now(timezone.utc)
    scored = []
    for pid, times, last in rows:
        age = (now - (last if last.tzinfo else last.replace(tzinfo=timezone.utc))).total_seconds() / 86400
        scored.append((times * scoring.recency_weight(age, BUY_AGAIN_HALF_LIFE_DAYS), str(pid), int(times)))
    scored.sort(key=lambda t: (-t[0], t[1]))
    top = scored[: limit * 3]
    eligible = await load_eligible(db, {pid for _s, pid, _n in top}, viewer, apply_excluded=False)
    items = []
    for _score, pid, times in top:
        if pid in eligible:
            p, shop, dist = eligible[pid]
            items.append(_item(p, shop, dist, "You bought this once" if times == 1 else f"You've bought this {times} times"))
        if len(items) >= limit:
            break
    return items
