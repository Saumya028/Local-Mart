# Recommendation engine

"Customers also bought", "Frequently bought together", "Recommended for you",
"Trending near you" and "Buy again" shelves, learned from order history.

## How it works

**Nightly batch (offline)** — `python -m scripts.build_recommendations`
1. Loads purchases (+ wishlist, + reviews) for opted-in customers.
2. Turns them into per-customer affinities (90-day half-life; repeats capped; 1–2★ reviews remove a product from that customer's profile; 4–5★ add a small boost).
3. Item-to-item similarity: shrunk cosine (`co_buyers / (co_buyers + 5)`), min **3** distinct co-buyers, top **30** neighbours per product. Two kinds: `also_bought` (whole histories) and `bought_together` (same order).
4. Popularity table (fallback + tie-break).
5. **Leave-last-out evaluation** (hit-rate@10, NDCG) against a popularity baseline.
6. **Quality gate** — promoted only if hit-rate ≥ baseline and hasn't regressed > 20 % vs the previous run. Otherwise the run is `rejected` and the previous model keeps serving.
7. Promotion is atomic (single active run, enforced by a partial unique index).

**Serving (online)** — indexed lookups only, never computes similarity per request.
Eligibility filter (active, in stock, shop active+approved, inside delivery radius, not an excluded category) → score → diversity (max 3/shop, 4/category) → tiered fallback (model → same-category/trending → rating/newest). 2 s DB statement timeout, Redis cache (120 s), fail-soft (an error returns an empty shelf, which the UI hides).

| Endpoint | Auth | Shelf |
|---|---|---|
| `GET /recommendations/product/{id}` | public | Customers also bought |
| `GET /recommendations/cart` | user | Frequently bought together |
| `GET /recommendations/home` | optional | Recommended for you / Trending near you |
| `GET /recommendations/buy-again` | user | Buy again (own orders, no model needed) |
| `POST /recommendations/events` | optional | impression / click / add_to_cart telemetry |
| `GET /admin/recommendations/status`, `/metrics?days=` | admin | health + shelf performance |
| `GET /health/recommendations` | public | `ok` / `no_model` / `disabled` = 200, `stale` = **503** |

## Privacy & fairness decisions
- Customers can opt out (Account → Settings): no personalised shelves, no events recorded, excluded from training. Takes effect at the next nightly build.
- **Pharmacy** (`RECO_EXCLUDED_CATEGORIES`) never appears in cross-customer recommendations. "Buy again" uses the customer's own history, so it may include it.
- **No sponsored boost** — sponsorship does not influence recommendations.
- Events are used for measurement only (never training) and deleted after 90 days.

## Configuration (env)
`RECO_ENABLED` (kill switch), `RECO_HOLDOUT_PCT` (0–50, control group that sees the popularity baseline — use ~10 to measure lift), `RECO_MIN_CO_BUYERS`, `RECO_HALF_LIFE_DAYS`, `RECO_MAX_ITEMS_PER_USER`, `RECO_NEIGHBORS_PER_PRODUCT`, `RECO_EXCLUDED_CATEGORIES`, `RECO_EVENT_RETENTION_DAYS`, `RECO_STALE_HOURS`, `RECO_MAX_REGRESSION`. See `.env.example`.

## Runbook
**Deploy:** `alembic upgrade head` (migration 0022), `pip install -r requirements-reco.txt` for the job image (the API image does not need numpy/scipy).
**Schedule:** nightly off-peak, e.g. 02:30 IST (`0 21 * * *` UTC) — Railway cron, or the scheduled job in `.github/workflows/ci.yml`.
**Exit codes:** `0` ok / nothing to do, `1` crashed, `2` rejected by gate, `3` another build running.
**Uptime monitor:** point it at `/health/recommendations` (alerts when the model is older than `RECO_STALE_HOURS`, default 36 h).

| Situation | Action |
|---|---|
| Shelves look wrong after a build | `python -m scripts.build_recommendations --rollback` |
| Build crashed and left a lock | rerun with `--force` |
| Want to preview a build | `--dry-run` (writes nothing) or `--no-promote` |
| Emergency off | `RECO_ENABLED=false` (shelves disappear, nothing else is affected) |
| Exit code 2 repeatedly | inspect `stats.gate_reasons` in Admin → Recommendations; usually too little data |
| Develop locally | `python -m scripts.seed_reco_demo` then build; `--clean` removes demo data |

**Measuring impact:** set `RECO_HOLDOUT_PCT=10`, then compare `model` vs `holdout` rows in Admin → Recommendations (CTR, add-to-cart rate, orders and revenue per 1 000 impressions; purchases are attributed to a click/add-to-cart on the same product within 7 days).
