"""
Recommendation shelves + their telemetry.

Every shelf endpoint is fail-soft: if anything goes wrong (or the feature is
switched off with RECO_ENABLED=false) the response is simply an empty shelf,
which the frontend hides — a recommendation problem must never break a
product, cart or home page.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import cart as cart_store
from app.core.config import settings
from app.core.db import get_db
from app.core.rate_limit import _check_and_increment
from app.core.recommendations import scoring, serving
from app.core.security import bearer_scheme, get_current_user
from app.core.utils import parse_uuid_or_404
from app.models import Product, Profile, RecommendationEvent
from app.schemas.recommendation import RecoEventsRequest, RecoEventsResponse, RecoResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

EVENTS_PER_MINUTE = 300


async def optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Profile | None:
    """The signed-in customer if there is a valid session, else None (the
    home shelf and event intake serve visitors too). A bad/expired token is
    treated as 'not signed in' rather than an error — these are optional."""
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def _empty(surface: str) -> RecoResponse:
    return RecoResponse(surface=surface, items=[])


@router.get("/product/{product_id}", response_model=RecoResponse)
async def product_shelf(
    product_id: str,
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float | None = Query(default=None, gt=0, le=100),
    limit: int = Query(default=8, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
):
    """"Customers also bought" — public, depends only on the product."""
    pid = parse_uuid_or_404(product_id, "Product")
    if not settings.reco_enabled:
        return _empty("product")
    try:
        await serving.start_request(db)
        viewer = await serving.resolve_viewer(db, lat, lng, radius_km)
        items, run_id = await serving.recommend_for_product(db, pid, viewer, limit)
        return RecoResponse(surface="product", run_id=run_id, variant="model", items=items)
    except Exception:
        logger.exception("product recommendations failed")
        return _empty("product")


@router.get("/cart", response_model=RecoResponse)
async def cart_shelf(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float | None = Query(default=None, gt=0, le=100),
    limit: int = Query(default=6, ge=1, le=20),
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """"Frequently bought together" for the current cart's contents."""
    if not settings.reco_enabled:
        return _empty("cart")
    try:
        cart = await cart_store.get_cart_items(user.id)
        await serving.start_request(db)
        viewer = await serving.resolve_viewer(db, lat, lng, radius_km)
        items, run_id = await serving.recommend_for_cart(db, cart, viewer, limit)
        return RecoResponse(surface="cart", run_id=run_id, variant="model", items=items)
    except Exception:
        logger.exception("cart recommendations failed")
        return _empty("cart")


@router.get("/home", response_model=RecoResponse)
async def home_shelf(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float | None = Query(default=None, gt=0, le=100),
    limit: int = Query(default=8, ge=1, le=20),
    user: Profile | None = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
):
    """"Recommended for you" when signed in (and opted in), otherwise
    "Trending near you"."""
    if not settings.reco_enabled:
        return _empty("home")
    try:
        await serving.start_request(db)
        viewer = await serving.resolve_viewer(db, lat, lng, radius_km)
        items, run_id, variant = await serving.recommend_for_home(db, user, viewer, limit)
        return RecoResponse(surface="home", run_id=run_id, variant=variant, items=items)
    except Exception:
        logger.exception("home recommendations failed")
        return _empty("home")


@router.get("/buy-again", response_model=RecoResponse)
async def buy_again_shelf(
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    radius_km: float | None = Query(default=None, gt=0, le=100),
    limit: int = Query(default=8, ge=1, le=20),
    user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Products the customer has bought before — from their own orders."""
    if not settings.reco_enabled:
        return _empty("buy_again")
    try:
        await serving.start_request(db)
        viewer = await serving.resolve_viewer(db, lat, lng, radius_km)
        items = await serving.buy_again(db, user, viewer, limit)
        return RecoResponse(surface="buy_again", variant="baseline", items=items)
    except Exception:
        logger.exception("buy-again recommendations failed")
        return _empty("buy_again")


@router.post("/events", response_model=RecoEventsResponse)
async def record_events(
    payload: RecoEventsRequest,
    request: Request,
    user: Profile | None = Depends(optional_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Shelf telemetry (impression / click / add_to_cart), batched by the
    frontend. Used only to measure how well shelves perform (see
    /admin/recommendations/metrics) — never to train the model. Customers who
    opted out of personalization are not recorded at all, and unknown
    surfaces/events/products are silently dropped rather than failing the batch.
    """
    if not settings.reco_enabled or not payload.events:
        return RecoEventsResponse(recorded=0)
    if user is not None and user.personalization_opt_out:
        return RecoEventsResponse(recorded=0)

    who = f"user:{user.id}" if user else f"ip:{request.client.host if request.client else 'unknown'}"
    await _check_and_increment(f"ratelimit:reco_events:{who}", EVENTS_PER_MINUTE, 60)

    valid = [
        e
        for e in payload.events
        if e.surface in scoring.SURFACES and e.event in scoring.EVENTS and e.variant in scoring.VARIANTS
    ]
    if not valid:
        return RecoEventsResponse(recorded=0)
    known = set(
        (await db.execute(select(Product.id).where(Product.id.in_({e.product_id for e in valid})))).scalars().all()
    )
    rows = [
        {
            "user_id": user.id if user else None,
            "surface": e.surface,
            "event": e.event,
            "product_id": e.product_id,
            "position": e.position,
            "run_id": e.run_id,
            "variant": e.variant,
        }
        for e in valid
        if e.product_id in known
    ]
    if rows:
        await db.execute(insert(RecommendationEvent), rows)
        await db.commit()
    return RecoEventsResponse(recorded=len(rows))
