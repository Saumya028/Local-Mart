"""
Offline accuracy check used as the promote gate (OFFLINE only — needs scipy).

Leave-last-out: for every customer with >= 2 distinct purchased products,
hide their most recent purchase, build a model from everything else, and ask
"is the hidden product in the top-k shelf we would have shown?". Compared
against a popularity-only baseline. The shelf is produced by the SAME
rank_candidates() the API uses, topped up with popular products exactly as
serving tops up with trending, so the number reflects what customers see.
"""
from collections import defaultdict
from datetime import datetime

from app.core.recommendations import scoring
from app.core.recommendations.builder import (
    BuildParams,
    compute_item_similarity,
    compute_popularity,
)

HISTORY_ITEMS = 20  # same cap serving uses


def _rank_of(items: list[str], target: str) -> int | None:
    try:
        return items.index(target) + 1
    except ValueError:
        return None


def evaluate(
    purchases: list[tuple],
    wishlist: list[tuple],
    reviews: list[tuple],
    *,
    now: datetime,
    params: BuildParams,
    k: int = 10,
) -> dict:
    # most recent purchased product per customer
    last_ts: dict[str, dict[str, datetime]] = defaultdict(dict)
    for u, p, _status, ts, _oid in purchases:
        u, p = str(u), str(p)
        if p not in last_ts[u] or ts > last_ts[u][p]:
            last_ts[u][p] = ts
    held: dict[str, str] = {}
    for u, prods in last_ts.items():
        if len(prods) >= 2:
            held[u] = max(prods.items(), key=lambda kv: (kv[1], kv[0]))[0]

    if len(held) < params.min_eval_users:
        return {"evaluated": False, "n_eval_users": len(held), "k": k, "reason": "too_few_users_with_2_products"}

    drop = {(u, p) for u, p in held.items()}
    train_p = [r for r in purchases if (str(r[0]), str(r[1])) not in drop]
    train_w = [r for r in wishlist if (str(r[0]), str(r[1])) not in drop]
    train_r = [r for r in reviews if (str(r[0]), str(r[1])) not in drop]
    data = scoring.interaction_weights(train_p, train_w, train_r, now=now, half_life_days=params.half_life_days)

    sims = compute_item_similarity(
        data.weights,
        min_co_buyers=params.min_co_buyers,
        top_k=params.top_k,
        max_items_per_user=params.max_items_per_user,
    )
    pop = compute_popularity(data.purchase_weights, data.buyers_30d)
    pop_score = {p: s for p, (s, _b) in pop.items()}
    pop_order = [p for p, _ in sorted(pop_score.items(), key=lambda kv: (-kv[1], kv[0]))]
    neighbors: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    for a, b, s, _n in sims:
        neighbors[a].append((b, s, pop_score.get(b, 0.0)))

    history: dict[str, dict[str, float]] = defaultdict(dict)
    for (u, p), w in data.weights.items():
        history[u][p] = w

    hits = base_hits = covered = 0
    ndcg = base_ndcg = 0.0
    for u, target in held.items():
        hist = dict(sorted(history.get(u, {}).items(), key=lambda kv: (-kv[1], kv[0]))[:HISTORY_ITEMS])
        exclude = set(hist)
        cf = [c for c, _s, _b in scoring.rank_candidates(hist, neighbors, exclude=exclude, limit=k)]
        if cf:
            covered += 1
        shelf = cf + [p for p in pop_order if p not in exclude and p not in set(cf)][: max(0, k - len(cf))]
        baseline = [p for p in pop_order if p not in exclude][:k]

        r = _rank_of(shelf, target)
        b = _rank_of(baseline, target)
        hits += r is not None
        base_hits += b is not None
        ndcg += scoring.ndcg_at_k(r, k)
        base_ndcg += scoring.ndcg_at_k(b, k)

    n = len(held)
    return {
        "evaluated": True,
        "k": k,
        "n_eval_users": n,
        "hit_rate": round(hits / n, 4),
        "ndcg": round(ndcg / n, 4),
        "baseline_hit_rate": round(base_hits / n, 4),
        "baseline_ndcg": round(base_ndcg / n, 4),
        "model_coverage_users": round(covered / n, 4),
        "catalog_coverage": round(len({a for a, *_ in sims}) / max(1, len(pop_score)), 4),
    }
