"""
OFFLINE model build — run nightly by scripts/build_recommendations.py (never
imported by the API; needs numpy/scipy from requirements-reco.txt).

Flow of run_build():
  1. refuse to start if another build is in progress (row-based lock — a
     Postgres advisory lock would not survive Supabase's pgbouncer pooler);
  2. load purchases / wishlists / reviews (excluding opted-out customers,
     shop staff buying from their own shop, fully-returned items and the
     excluded categories);
  3. turn them into per-customer affinities (scoring.interaction_weights);
  4. compute item-item similarity ("also bought" over whole histories and
     "bought together" within orders) and popularity;
  5. evaluate offline (evaluation.evaluate) and decide whether to promote;
  6. write rows under a new run id, then flip is_active in ONE transaction so
     customers see either the old model or the new one, never a mixture;
  7. prune old runs and expired telemetry.
"""
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import combinations

import numpy as np
from scipy import sparse
from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import invalidate
from app.core.config import settings
from app.core.order_status import RECOGNIZED_STATUSES
from app.core.recommendations import scoring
from app.models import (
    Order,
    OrderItem,
    Product,
    ProductPopularity,
    ProductReview,
    ProductSimilarity,
    Profile,
    RecommendationEvent,
    RecommendationRun,
    ReturnRequest,
    Shop,
    WishlistItem,
)

logger = logging.getLogger(__name__)

ACTIVE_RUN_CACHE_KEY = scoring.ACTIVE_RUN_CACHE_KEY
STALE_LOCK_AFTER = timedelta(hours=2)
KEEP_READY_RUNS = 3
WRITE_CHUNK = 4000  # 5 columns * 4000 stays under asyncpg's 32767-parameter limit


class BuildInProgress(Exception):
    pass


@dataclass
class BuildParams:
    min_co_buyers: int
    half_life_days: float
    max_items_per_user: int
    top_k: int
    excluded_categories: list[str]
    max_regression: float
    min_eval_users: int = 20

    @classmethod
    def from_settings(cls) -> "BuildParams":
        return cls(
            min_co_buyers=settings.reco_min_co_buyers,
            half_life_days=settings.reco_half_life_days,
            max_items_per_user=settings.reco_max_items_per_user,
            top_k=settings.reco_neighbors_per_product,
            excluded_categories=settings.reco_excluded_category_list,
            max_regression=settings.reco_max_regression,
        )


# --------------------------------------------------------------------------
# Pure model computation
# --------------------------------------------------------------------------


def _top_k_per_row(rows: np.ndarray, cols: np.ndarray, scores: np.ndarray, counts: np.ndarray, top_k: int):
    """Keeps the `top_k` highest-scoring entries of each row (vectorised)."""
    if len(rows) == 0:
        return rows, cols, scores, counts
    order = np.lexsort((-scores, rows))  # by row, then best score first
    rows, cols, scores, counts = rows[order], cols[order], scores[order], counts[order]
    starts = np.r_[0, np.flatnonzero(np.diff(rows)) + 1]
    sizes = np.diff(np.r_[starts, len(rows)])
    rank = np.arange(len(rows)) - np.repeat(starts, sizes)
    keep = rank < top_k
    return rows[keep], cols[keep], scores[keep], counts[keep]


def compute_item_similarity(
    weights: dict[tuple[str, str], float],
    *,
    min_co_buyers: int,
    top_k: int,
    max_items_per_user: int,
    shrink: float = scoring.SHRINKAGE,
) -> list[tuple[str, str, float, int]]:
    """
    Item-item cosine over customer affinity vectors, shrunk by support.
    Returns [(product_id, similar_product_id, score, co_buyers)] with at most
    `top_k` neighbours per product and only pairs shared by >= min_co_buyers
    DISTINCT customers (each customer counts once per pair, however much
    they bought — one account cannot manufacture a recommendation).
    """
    if not weights:
        return []

    by_user: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for (u, p), w in weights.items():
        if w > 0:
            by_user[u].append((w, p))

    users: dict[str, int] = {}
    items: dict[str, int] = {}
    r, c, d = [], [], []
    for u, lst in by_user.items():
        lst.sort(key=lambda t: (-t[0], t[1]))  # strongest first, deterministic ties
        for w, p in lst[:max_items_per_user]:
            r.append(users.setdefault(u, len(users)))
            c.append(items.setdefault(p, len(items)))
            d.append(w)
    if not items:
        return []

    W = sparse.csr_matrix((d, (r, c)), shape=(len(users), len(items)), dtype=np.float64)
    B = W.copy()
    B.data = np.ones_like(B.data)
    norms = np.sqrt(np.asarray(W.multiply(W).sum(axis=0)).ravel())

    C = (W.T @ W).tocoo()  # weighted co-affinity
    N = (B.T @ B).tocoo()  # distinct shared customers
    oc = np.lexsort((C.col, C.row))
    on = np.lexsort((N.col, N.row))
    rows, cols, co_w = C.row[oc], C.col[oc], C.data[oc]
    n = N.data[on]
    if not (np.array_equal(rows, N.row[on]) and np.array_equal(cols, N.col[on])):  # pragma: no cover
        raise RuntimeError("similarity matrices misaligned")

    mask = (rows != cols) & (n >= min_co_buyers)
    rows, cols, co_w, n = rows[mask], cols[mask], co_w[mask], n[mask]
    scores = (co_w / (norms[rows] * norms[cols])) * (n / (n + shrink))

    rows, cols, scores, n = _top_k_per_row(rows, cols, scores, n, top_k)
    names = [""] * len(items)
    for p, i in items.items():
        names[i] = p
    return [(names[a], names[b], float(s), int(k)) for a, b, s, k in zip(rows, cols, scores, n)]


def compute_basket_similarity(
    baskets: list[tuple[str, float, list[str]]],
    *,
    min_co_buyers: int,
    top_k: int,
    shrink: float = scoring.SHRINKAGE,
) -> list[tuple[str, str, float, int]]:
    """
    "Bought together" — same cosine idea, but over co-occurrence inside one
    order. Per customer each pair counts once (the strongest basket wins).
    """
    user_items: dict[str, dict[str, float]] = defaultdict(dict)
    user_pairs: dict[str, dict[tuple[str, str], float]] = defaultdict(dict)
    for u, w, items in baskets:
        ui, up = user_items[u], user_pairs[u]
        for it in items:
            ui[it] = max(ui.get(it, 0.0), w)
        for pair in combinations(items, 2):  # items are sorted => stable key
            up[pair] = max(up.get(pair, 0.0), w)

    sumsq: dict[str, float] = defaultdict(float)
    for ui in user_items.values():
        for it, w in ui.items():
            sumsq[it] += w * w
    pair_w: dict[tuple[str, str], float] = defaultdict(float)
    pair_n: dict[tuple[str, str], int] = defaultdict(int)
    for up in user_pairs.values():
        for pair, w in up.items():
            pair_w[pair] += w * w
            pair_n[pair] += 1

    neighbors: dict[str, list[tuple[float, str, int]]] = defaultdict(list)
    for (a, b), n in pair_n.items():
        if n < min_co_buyers:
            continue
        s = scoring.shrunk_cosine(pair_w[(a, b)], sumsq[a] ** 0.5, sumsq[b] ** 0.5, n, shrink)
        neighbors[a].append((s, b, n))
        neighbors[b].append((s, a, n))

    out = []
    for a, lst in neighbors.items():
        lst.sort(key=lambda t: (-t[0], t[1]))
        out += [(a, b, s, n) for s, b, n in lst[:top_k]]
    return out


def compute_popularity(
    purchase_weights: dict[tuple[str, str], float], buyers_30d: dict[str, int]
) -> dict[str, tuple[float, int]]:
    """product -> (recency-weighted distinct-buyer score, distinct buyers in 30 days)."""
    score: dict[str, float] = defaultdict(float)
    for (_u, p), w in purchase_weights.items():
        score[p] += w
    return {p: (s, buyers_30d.get(p, 0)) for p, s in score.items()}


def decide_promotion(
    *, n_similarity: int, n_popularity: int, evaluation: dict, previous_hit_rate: float | None, max_regression: float
) -> tuple[bool, list[str]]:
    """The quality gate. Returns (promote?, reasons-if-not / notes)."""
    if n_similarity == 0 and n_popularity == 0:
        return False, ["no_data"]
    notes: list[str] = []
    if not evaluation.get("evaluated"):
        return True, ["unevaluated_too_few_users"]
    hit, base = evaluation["hit_rate"], evaluation["baseline_hit_rate"]
    if hit + 1e-12 < base:
        return False, [f"worse_than_popularity ({hit:.3f} < {base:.3f})"]
    if previous_hit_rate and hit + 1e-12 < previous_hit_rate * (1 - max_regression):
        return False, [f"regression_vs_previous ({hit:.3f} vs {previous_hit_rate:.3f})"]
    return True, notes


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------


def _eligible_buyer_conditions():
    """Customers whose data may train the model."""
    return [
        Profile.personalization_opt_out.is_(False),
        Profile.is_suspended.is_(False),
        # a shop owner / staff member buying from their OWN shop says nothing
        # about what customers like (and is the easiest way to game a ranking)
        Shop.owner_id != Order.user_id,
        or_(Profile.shop_id.is_(None), Profile.shop_id != Order.shop_id),
    ]


async def load_interactions(db: AsyncSession, params: BuildParams):
    returned = (
        select(ReturnRequest.order_item_id, func.sum(ReturnRequest.quantity).label("qty"))
        .where(ReturnRequest.status == "completed")
        .group_by(ReturnRequest.order_item_id)
        .subquery()
    )
    purchase_stmt = (
        select(
            Order.user_id,
            OrderItem.product_id,
            Order.status,
            func.coalesce(Order.delivered_at, Order.created_at),
            Order.id,
        )
        .select_from(OrderItem)
        .join(Order, Order.id == OrderItem.order_id)
        .join(Shop, Shop.id == Order.shop_id)
        .join(Profile, Profile.id == Order.user_id)
        .join(Product, Product.id == OrderItem.product_id)
        .outerjoin(returned, returned.c.order_item_id == OrderItem.id)
        .where(
            Order.status.in_(RECOGNIZED_STATUSES),
            func.coalesce(returned.c.qty, 0) < OrderItem.quantity,  # fully returned items don't count
            *_eligible_buyer_conditions(),
        )
    )
    wishlist_stmt = (
        select(WishlistItem.user_id, WishlistItem.product_id, WishlistItem.created_at)
        .join(Profile, Profile.id == WishlistItem.user_id)
        .join(Product, Product.id == WishlistItem.product_id)
        .where(Profile.personalization_opt_out.is_(False), Profile.is_suspended.is_(False))
    )
    review_stmt = (
        select(ProductReview.user_id, ProductReview.product_id, ProductReview.rating)
        .join(Profile, Profile.id == ProductReview.user_id)
        .where(ProductReview.is_hidden.is_(False), Profile.personalization_opt_out.is_(False))
    )
    if params.excluded_categories:
        purchase_stmt = purchase_stmt.where(Product.category.notin_(params.excluded_categories))
        wishlist_stmt = wishlist_stmt.where(Product.category.notin_(params.excluded_categories))

    purchases = [tuple(r) for r in (await db.execute(purchase_stmt)).all()]
    wishlist = [tuple(r) for r in (await db.execute(wishlist_stmt)).all()]
    reviews = [tuple(r) for r in (await db.execute(review_stmt)).all()]
    return purchases, wishlist, reviews


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------


async def _write_rows(db: AsyncSession, model, rows: list[dict]) -> None:
    for i in range(0, len(rows), WRITE_CHUNK):
        await db.execute(insert(model), rows[i : i + WRITE_CHUNK])


async def run_build(
    db: AsyncSession,
    *,
    promote: bool = True,
    force: bool = False,
    dry_run: bool = False,
    now: datetime | None = None,
    params: BuildParams | None = None,
) -> RecommendationRun:
    from app.core.recommendations.evaluation import evaluate  # local: keeps import graph simple

    params = params or BuildParams.from_settings()
    now = now or datetime.now(timezone.utc)
    t0 = time.monotonic()

    # ---- 1. lock ---------------------------------------------------------
    in_progress = (
        await db.execute(
            select(RecommendationRun.id).where(
                RecommendationRun.status == "building",
                RecommendationRun.started_at > now - STALE_LOCK_AFTER,
            )
        )
    ).first()
    if in_progress and not force:
        raise BuildInProgress("another recommendation build is already running")
    # a "building" row older than the lock window is a crashed run — mark it
    await db.execute(
        update(RecommendationRun)
        .where(RecommendationRun.status == "building", RecommendationRun.started_at <= now - STALE_LOCK_AFTER)
        .values(status="failed", error="abandoned (no heartbeat)", finished_at=now)
    )

    run = RecommendationRun(id=uuid.uuid4(), status="building", stats={})
    if not dry_run:
        db.add(run)
    await db.commit()

    try:
        # ---- 2-3. load + weights ---------------------------------------
        purchases, wishlist, reviews = await load_interactions(db, params)
        data = scoring.interaction_weights(
            purchases, wishlist, reviews, now=now, half_life_days=params.half_life_days
        )

        # ---- 4. models -------------------------------------------------
        also = compute_item_similarity(
            data.weights,
            min_co_buyers=params.min_co_buyers,
            top_k=params.top_k,
            max_items_per_user=params.max_items_per_user,
        )
        together = compute_basket_similarity(
            data.baskets, min_co_buyers=params.min_co_buyers, top_k=params.top_k
        )
        popularity = compute_popularity(data.purchase_weights, data.buyers_30d)

        # ---- 5. evaluate + gate ----------------------------------------
        evaluation = evaluate(purchases, wishlist, reviews, now=now, params=params)
        previous = (
            await db.execute(
                select(RecommendationRun.stats).where(RecommendationRun.is_active.is_(True))
            )
        ).scalar_one_or_none()
        previous_hit = ((previous or {}).get("evaluation") or {}).get("hit_rate")
        ok, reasons = decide_promotion(
            n_similarity=len(also) + len(together),
            n_popularity=len(popularity),
            evaluation=evaluation,
            previous_hit_rate=previous_hit,
            max_regression=params.max_regression,
        )

        stats = {
            "customers": len({u for u, _ in data.weights}),
            "purchase_rows": len(purchases),
            "wishlist_rows": len(wishlist),
            "products_with_also_bought": len({a for a, *_ in also}),
            "products_with_bought_together": len({a for a, *_ in together}),
            "also_bought_rows": len(also),
            "bought_together_rows": len(together),
            "popularity_rows": len(popularity),
            "evaluation": evaluation,
            "gate_reasons": reasons,
            "duration_seconds": round(time.monotonic() - t0, 2),
        }
        logger.info("reco build computed", extra={"run_id": str(run.id), **{k: v for k, v in stats.items() if k != "evaluation"}})

        if dry_run:
            run.status = "ready" if ok else "rejected"
            run.stats = stats
            return run

        if not ok:
            run.status = "rejected"
            run.stats = stats
            run.finished_at = datetime.now(timezone.utc)
            await db.merge(run)
            await db.commit()
            logger.warning("reco build REJECTED", extra={"run_id": str(run.id), "reasons": reasons})
            return run

        # ---- 6. write + atomic promote ---------------------------------
        existing = set((await db.execute(select(Product.id))).scalars().all())
        existing_s = {str(p) for p in existing}
        sim_rows = [
            {"run_id": run.id, "kind": kind, "product_id": uuid.UUID(a), "similar_product_id": uuid.UUID(b),
             "score": s, "co_buyers": n}
            for kind, rows in (("also_bought", also), ("bought_together", together))
            for a, b, s, n in rows
            if a in existing_s and b in existing_s
        ]
        pop_rows = [
            {"run_id": run.id, "product_id": uuid.UUID(p), "score": s, "buyers_30d": b}
            for p, (s, b) in popularity.items()
            if p in existing_s
        ]
        await _write_rows(db, ProductSimilarity, sim_rows)
        await _write_rows(db, ProductPopularity, pop_rows)

        run.status = "ready"
        run.stats = stats
        run.finished_at = datetime.now(timezone.utc)
        await db.merge(run)
        if promote:
            await db.execute(
                update(RecommendationRun).where(RecommendationRun.is_active.is_(True)).values(is_active=False)
            )
            await db.execute(update(RecommendationRun).where(RecommendationRun.id == run.id).values(is_active=True))
            run.is_active = True
        await db.commit()
        await invalidate(ACTIVE_RUN_CACHE_KEY)

        # ---- 7. housekeeping -------------------------------------------
        await prune(db, now=now)
        return run
    except Exception as exc:
        await db.rollback()
        await db.execute(
            update(RecommendationRun)
            .where(RecommendationRun.id == run.id)
            .values(status="failed", error=str(exc)[:1000], finished_at=datetime.now(timezone.utc))
        )
        await db.commit()
        logger.exception("reco build FAILED", extra={"run_id": str(run.id)})
        raise


async def prune(db: AsyncSession, *, now: datetime) -> dict:
    """Keeps the active run + the newest few ready runs (for rollback);
    drops rejected/failed runs after a week and telemetry past retention."""
    keep_ids = set(
        (
            await db.execute(
                select(RecommendationRun.id)
                .where(RecommendationRun.status == "ready")
                .order_by(RecommendationRun.started_at.desc())
                .limit(KEEP_READY_RUNS)
            )
        ).scalars().all()
    )
    active = (
        await db.execute(select(RecommendationRun.id).where(RecommendationRun.is_active.is_(True)))
    ).scalar_one_or_none()
    if active:
        keep_ids.add(active)
    old_runs = await db.execute(
        delete(RecommendationRun).where(
            RecommendationRun.id.notin_(keep_ids) if keep_ids else True,
            RecommendationRun.status != "building",
            or_(
                RecommendationRun.status == "ready",
                RecommendationRun.started_at < now - timedelta(days=7),
            ),
        )
    )
    old_events = await db.execute(
        delete(RecommendationEvent).where(
            RecommendationEvent.created_at < now - timedelta(days=settings.reco_event_retention_days)
        )
    )
    await db.commit()
    return {"runs_deleted": old_runs.rowcount, "events_deleted": old_events.rowcount}


async def rollback_to_previous(db: AsyncSession) -> uuid.UUID | None:
    """Operational escape hatch: re-activate the newest ready run that is not
    the current one. Returns its id (None if there is nothing to roll back to)."""
    current = (
        await db.execute(select(RecommendationRun.id).where(RecommendationRun.is_active.is_(True)))
    ).scalar_one_or_none()
    prev = (
        await db.execute(
            select(RecommendationRun.id)
            .where(RecommendationRun.status == "ready", RecommendationRun.id != current)
            .order_by(RecommendationRun.started_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if prev is None:
        return None
    await db.execute(update(RecommendationRun).where(RecommendationRun.is_active.is_(True)).values(is_active=False))
    await db.execute(update(RecommendationRun).where(RecommendationRun.id == prev).values(is_active=True))
    await db.commit()
    await invalidate(ACTIVE_RUN_CACHE_KEY)
    return prev
