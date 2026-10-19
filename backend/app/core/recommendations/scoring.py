"""
Pure functions (no DB, no numpy) used by BOTH the nightly builder/evaluator
and the request-time server, so what is evaluated offline is exactly what is
served online.
"""
import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.order_status import TERMINAL_STATUSES

# Weights per kind of signal (relative strength of "this customer likes it").
PURCHASE_TERMINAL_WEIGHT = 1.0  # delivered / picked up
PURCHASE_PENDING_WEIGHT = 0.6  # placed but not yet fulfilled (could still be cancelled)
WISHLIST_WEIGHT = 0.5
MAX_AFFINITY = 1.5  # repeat purchases help, but with a ceiling
POSITIVE_REVIEW_BOOST = 0.2  # rating >= 4
NEGATIVE_REVIEW_MAX_RATING = 2  # rating <= 2 removes the signal entirely
MAX_BASKET_SIZE = 30  # bigger orders say little about "bought together"
SHRINKAGE = 5.0  # pulls low-support similarities toward 0

# Redis key holding the active run id (the builder busts it on promote/rollback;
# the API caches it for a minute). Lives here so neither side imports the other.
ACTIVE_RUN_CACHE_KEY = "reco:active_run"

# Surfaces / events accepted by the telemetry endpoint.
SURFACES = ("product", "cart", "home", "buy_again")
EVENTS = ("impression", "click", "add_to_cart")
VARIANTS = ("model", "baseline", "holdout")


def recency_weight(age_days: float, half_life_days: float) -> float:
    """1.0 today, 0.5 after one half-life, 0.25 after two, ..."""
    if half_life_days <= 0:
        return 1.0
    return 0.5 ** (max(age_days, 0.0) / half_life_days)


def shrunk_cosine(co_weight: float, norm_a: float, norm_b: float, co_buyers: int, shrink: float = SHRINKAGE) -> float:
    """
    Cosine similarity between two items' customer vectors, multiplied by
    n/(n+shrink): a pair seen by 3 customers is trusted much less than the
    same raw cosine seen by 300. (`co_weight` is the dot product, `norm_*`
    the vector lengths, `co_buyers` the number of distinct shared customers.)
    """
    if norm_a <= 0 or norm_b <= 0 or co_buyers <= 0:
        return 0.0
    return (co_weight / (norm_a * norm_b)) * (co_buyers / (co_buyers + shrink))


def holdout_bucket(user_id: str) -> int:
    """Stable 0-99 bucket for a user — same user, same bucket, forever."""
    return int(hashlib.sha256(str(user_id).encode()).hexdigest()[:8], 16) % 100


def in_holdout(user_id: str | None, holdout_pct: int) -> bool:
    """True when this logged-in user is in the control group that gets the
    popularity baseline instead of the model. Anonymous visitors are never
    in the holdout (they can't be assigned stably)."""
    if user_id is None or holdout_pct <= 0:
        return False
    return holdout_bucket(user_id) < min(holdout_pct, 50)


def geo_bucket(lat: float | None, lng: float | None) -> str:
    """Rounds a location to ~1 km so cache keys are shared by neighbours."""
    if lat is None or lng is None:
        return "none"
    return f"{round(lat, 2)}:{round(lng, 2)}"


@dataclass
class InteractionData:
    # (user_id, product_id) -> affinity weight in (0, MAX_AFFINITY]
    weights: dict[tuple[str, str], float] = field(default_factory=dict)
    # (user_id, basket weight, product ids) — orders with >= 2 distinct products
    baskets: list[tuple[str, float, list[str]]] = field(default_factory=list)
    # (user_id, product_id) -> purchase-only weight (for popularity)
    purchase_weights: dict[tuple[str, str], float] = field(default_factory=dict)
    # product_id -> distinct buyers in the last 30 days
    buyers_30d: dict[str, int] = field(default_factory=dict)


def interaction_weights(
    purchases: list[tuple],  # (user_id, product_id, order_status, ts, order_id)
    wishlist: list[tuple],  # (user_id, product_id, ts)
    reviews: list[tuple],  # (user_id, product_id, rating)
    *,
    now: datetime,
    half_life_days: float,
) -> InteractionData:
    """
    Turns raw rows into per-(customer, product) affinities.

    - Purchases: recency-decayed, full weight when fulfilled, 0.6 while
      pending; repeats add up to MAX_AFFINITY.
    - Wishlist: weaker (0.5, decayed); never lowers an existing purchase weight.
    - Reviews: 4-5 stars add a small boost; 1-2 stars REMOVE the product from
      that customer's profile (they didn't like it, so it can't vouch for
      anything — nor appear in baskets or popularity).
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    negative = {(str(u), str(p)) for u, p, r in reviews if r <= NEGATIVE_REVIEW_MAX_RATING}
    positive = {(str(u), str(p)) for u, p, r in reviews if r >= 4}

    data = InteractionData()
    orders: dict[str, tuple[str, float, set[str]]] = {}
    thirty_day_buyers: dict[str, set[str]] = {}

    for user_id, product_id, status, ts, order_id in purchases:
        u, p = str(user_id), str(product_id)
        if (u, p) in negative:
            continue
        ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        age = (now - ts).total_seconds() / 86400
        base = PURCHASE_TERMINAL_WEIGHT if status in TERMINAL_STATUSES else PURCHASE_PENDING_WEIGHT
        w = base * recency_weight(age, half_life_days)
        data.purchase_weights[(u, p)] = min(MAX_AFFINITY, data.purchase_weights.get((u, p), 0.0) + w)
        if age <= 30:
            thirty_day_buyers.setdefault(p, set()).add(u)
        entry = orders.setdefault(str(order_id), (u, w, set()))
        entry[2].add(p)
        # the basket weight is the strongest line's weight (all lines share a date/status)
        orders[str(order_id)] = (u, max(entry[1], w), entry[2])

    data.weights = dict(data.purchase_weights)

    for user_id, product_id, ts in wishlist:
        u, p = str(user_id), str(product_id)
        if (u, p) in negative:
            continue
        ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        w = WISHLIST_WEIGHT * recency_weight((now - ts).total_seconds() / 86400, half_life_days)
        data.weights[(u, p)] = max(data.weights.get((u, p), 0.0), w)

    for key in positive:
        if key in data.purchase_weights:
            data.weights[key] = min(MAX_AFFINITY, data.weights[key] + POSITIVE_REVIEW_BOOST)

    for u, w, items in orders.values():
        if 2 <= len(items) <= MAX_BASKET_SIZE:
            data.baskets.append((u, w, sorted(items)))

    data.buyers_30d = {p: len(us) for p, us in thirty_day_buyers.items()}
    return data


def rank_candidates(
    history: dict[str, float],
    neighbors: dict[str, list[tuple[str, float, float]]],
    *,
    exclude: set[str],
    limit: int,
    pop_weight: float = 0.05,
) -> list[tuple[str, float, str]]:
    """
    Scores candidate products for one customer (or one cart / one product).

    history:   {product_id: affinity weight} — what the person bought/saved/is viewing
    neighbors: {history_product_id: [(candidate_id, similarity, popularity), ...]}
    Returns [(candidate_id, score, because_product_id)] best first, where
    score = (sum of weight*similarity over history, scaled to 0-1)
            + pop_weight * (candidate popularity scaled to 0-1)
    and `because` is the history item that contributed most. Candidates with
    no collaborative signal are never returned here (serving fills those
    from the popularity/category fallbacks).
    """
    cf: dict[str, float] = {}
    best_src: dict[str, tuple[float, str]] = {}
    pop: dict[str, float] = {}
    for src, w in history.items():
        for cand, sim, popularity in neighbors.get(src, ()):
            if cand in exclude:
                continue
            contrib = w * sim
            cf[cand] = cf.get(cand, 0.0) + contrib
            if contrib > best_src.get(cand, (-1.0, ""))[0]:
                best_src[cand] = (contrib, src)
            pop[cand] = max(pop.get(cand, 0.0), popularity)
    if not cf:
        return []
    max_cf = max(cf.values()) or 1.0
    max_pop = max(pop.values()) or 1.0
    scored = [
        (cand, cf[cand] / max_cf + pop_weight * (pop.get(cand, 0.0) / max_pop), best_src[cand][1])
        for cand in cf
    ]
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored[:limit]


def apply_diversity(
    ranked: list[tuple[str, float, str]],
    shop_of: dict[str, str],
    category_of: dict[str, str],
    *,
    max_per_shop: int,
    max_per_category: int,
    limit: int,
) -> list[tuple[str, float, str]]:
    """
    Greedy re-rank so a shelf isn't eight products from one shop/category:
    walk best-first, skipping anything that would exceed a cap; then, if the
    shelf is still short, top it up with the skipped ones in score order —
    variety is a preference, never a reason to show fewer products.
    """
    picked: list[tuple[str, float, str]] = []
    skipped: list[tuple[str, float, str]] = []
    shops: dict[str, int] = {}
    cats: dict[str, int] = {}
    for item in ranked:
        pid = item[0]
        shop, cat = shop_of.get(pid, ""), category_of.get(pid, "")
        if shops.get(shop, 0) >= max_per_shop or cats.get(cat, 0) >= max_per_category:
            skipped.append(item)
            continue
        picked.append(item)
        shops[shop] = shops.get(shop, 0) + 1
        cats[cat] = cats.get(cat, 0) + 1
        if len(picked) >= limit:
            return picked
    return (picked + skipped)[:limit]


def ndcg_at_k(rank: int | None, k: int) -> float:
    """NDCG for a single relevant item at 1-based `rank` (None = missed)."""
    if rank is None or rank > k:
        return 0.0
    return 1.0 / math.log2(rank + 1)
