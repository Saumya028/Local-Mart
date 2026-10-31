# LocalMart Backend (FastAPI)

## What exists right now (Phase 0 through 7)

```
app/
  main.py                # app entrypoint: logging/Sentry init, middleware, router registration
  core/
    config.py, db.py, redis_client.py, security.py
    cache.py, utils.py, cart.py, idempotency.py
    request_context.py (new)   # per-request ID, via contextvar
    logging_config.py (new)    # structured JSON logging
    rate_limit.py (new)        # Redis-backed fixed-window rate limiter
    observability.py (new)     # optional Sentry init (no-op without SENTRY_DSN)
  models/
    base.py, profile.py, address.py, shop.py, product.py
    order.py, order_item.py, payment.py, audit_log.py
  schemas/
    profile.py, category.py, address.py, shop.py, product.py, order.py
    dashboard.py, admin.py
  routers/
    health.py, auth.py, categories.py, products.py
    cart.py, addresses.py
    shops.py, orders.py, shop_dashboard.py, admin.py
migrations/                 # Alembic (0001-0008 — 0005 added the Admin Panel's shop-approval/user-suspend/settings tables, 0006 added shop verification documents + rejection reason, 0007 added profile phone + wishlist for the My Account page, 0008 made profiles.email nullable for phone-only Login accounts)
scripts/
  seed.py, promote_user.py
  backup_restore_check.sh (new)   # backup/restore verification runbook
tests/ (new)
  conftest.py, test_app_wiring.py, test_require_role.py
pyproject.toml (new)         # ruff lint config
requirements-dev.txt (new)   # pytest, ruff - on top of requirements.txt
```

## Setup

One new migration this phase - run it before anything else:

```bash
alembic upgrade head
```

Two new optional env vars (both fine left blank - see `.env.example`):
`SENTRY_DSN`, `LOG_LEVEL`. `FRONTEND_ORIGIN` now accepts a comma-separated
list if you need more than one allowed origin (e.g. staging + prod).

## Bootstrapping your first admin

The Admin Panel (Phase 6) is admin-only, and there's a chicken-and-egg
problem: you need an admin account to grant admin access through the UI.
So `scripts/promote_user.py` exists purely as the one-time bootstrap step:

```bash
python -m scripts.promote_user your-email@example.com admin
```

Every promotion/demotion after that - including granting further admins
- happens through `PATCH /admin/users/{id}/role` (the Admin Panel UI),
which is logged to `audit_logs`; the script itself is deliberately
**not** logged, since it's a direct database operation run outside the
running application.

## Try the Admin Panel endpoints (Phase 6)

```bash
# Platform-wide metrics (GMV, order counts, active shops, etc.):
curl http://localhost:8000/admin/metrics -H "Authorization: Bearer ADMIN_TOKEN"

# List/search users, then approve someone as a seller:
curl http://localhost:8000/admin/users?q=someone@example.com -H "Authorization: Bearer ADMIN_TOKEN"
curl -X PATCH http://localhost:8000/admin/users/USER_ID/role \
  -H "Authorization: Bearer ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"role": "shop_owner"}'

# Moderate any shop on the platform (not just your own):
curl http://localhost:8000/admin/shops -H "Authorization: Bearer ADMIN_TOKEN"
curl -X PATCH http://localhost:8000/admin/shops/SHOP_ID/status \
  -H "Authorization: Bearer ADMIN_TOKEN" -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# See every admin action ever taken, newest first:
curl http://localhost:8000/admin/audit-log -H "Authorization: Bearer ADMIN_TOKEN"
```

## Try the new hardening features (Phase 7)

```bash
# Rate limiting: the 11th checkout attempt in a minute for the same user gets a 429
for i in $(seq 1 11); do
  curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8000/orders \
    -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" \
    -H "Idempotency-Key: test-$i" -d '{"address_id": "..."}'
done

# Request ID: every response echoes back the one it was given (or generates one)
curl -i http://localhost:8000/health | grep -i x-request-id

# Structured logs: every line is one JSON object, request_id included
uvicorn app.main:app --reload | head -5
```

## Running the new checks locally

```bash
pip install -r requirements-dev.txt

ruff check .                 # lint
pytest tests/ -v             # the (small, honest) test suite - see below
pip-audit -r requirements.txt --ignore-vuln PYSEC-2026-161 \
  --ignore-vuln PYSEC-2026-249 --ignore-vuln PYSEC-2026-248 \
  --ignore-vuln PYSEC-2026-2281 --ignore-vuln PYSEC-2026-2280
```

All three now run on every push/PR - see `../.github/workflows/ci.yml`,
which also finally closes out Phase 0's original "Basic CI... runs lint
+ build on every push" line item. It never actually got built until now.

## What this test suite does and doesn't cover

Worth being direct about this rather than letting a `tests/` folder imply
more than it delivers. Phases 1, 3, 5, and 6 each had a "don't skip:
write tests" line in the roadmap - signup/login, checkout failure paths,
shop-ownership 403s, admin privilege escalation. **None of those were
ever actually written.** This phase adds the first tests this project
has ever had, and they are deliberately narrow:

- `test_app_wiring.py` - the app imports cleanly, every router is
  actually registered, CORS isn't accidentally wildcarded, the OpenAPI
  schema generates. Cheap, but this exact class of test has caught real
  "the router file exists but nobody added `include_router`" bugs
  before.
- `test_require_role.py` - unit tests for the RBAC dependency every
  ownership check in the app is built on, including the specific
  scenario `admin.py`'s whole router depends on (a `shop_owner` - a
  real, privileged role elsewhere - must still be refused on an
  admin-only route).

Neither spins up a real Postgres or Redis (see `tests/conftest.py`), so
neither of these catches: a checkout race condition, a webhook arriving
twice, RLS policies actually being enforced, or a shop owner reaching
another shop's order by ID. Those integration tests are the real,
still-open gap from Phases 3/5/6 - closing it properly needs test
database/Redis fixtures (e.g. `pytest` service containers or
`testcontainers`), which is a bigger lift than this hardening pass, not
a reason to pretend the gap is closed. Flagging it here so it's a known
follow-up, not a surprise later.

## What changed and why (Phase 7)

- **`core/rate_limit.py` - Redis-backed, fixed-window, fails open.**
  Applied to checkout (10/min per user - the most expensive endpoint in
  the app, since it does row-locking stock updates) and `/auth/me` (30/min per IP - the one
  auth-adjacent endpoint this backend owns; real login/signup lives
  entirely in Supabase Auth, which the frontend calls directly and never
  routes through this backend, so there's no login endpoint here to
  brute-force in the traditional sense). "Fails open" means a Redis
  outage lets requests through rather than taking down checkout - same
  philosophy as `cache.py`'s existing fail-open behavior on a cache miss.
- **`core/request_context.py` + `RequestIDMiddleware` in `main.py`.**
  Every request gets an ID - from the caller's own `X-Request-ID` header
  if it sent one (the frontend's `apiClient.ts` always does), else a
  fresh UUID - stored in a contextvar so every log line anywhere in the
  call stack picks it up automatically, and echoed back as a response
  header. This delivers the backend half of "trace one request across
  frontend -> backend -> DB." The "-> DB" half is honestly weaker: we
  don't tag raw Postgres query logs with this ID, since that needs
  server-side log configuration on whatever's hosting Postgres
  (Supabase's own `log_line_prefix`), which is outside this app's
  control - a DB-side slow query still has to be correlated by
  timestamp, not request_id, until that's set up separately.
- **`core/observability.py` - Sentry, entirely optional.** A true no-op
  (doesn't even import `sentry_sdk`) when `SENTRY_DSN` is unset, so
  nothing here requires a Sentry account to run this project. Once a DSN
  is set, FastAPI + SQLAlchemy instrumentation turns on automatically -
  no other code changes needed. `send_default_pii=False` is explicit:
  never attach cookies or request bodies to an error report by default.
- **A catch-all `Exception` handler in `main.py`.** Previously only
  `RedisError` was handled gracefully; any other unhandled exception
  either leaked a raw traceback or showed up as an opaque connection
  reset. Now every unhandled exception gets logged (with its request_id,
  and to Sentry if configured) and returns one clean JSON 500 - "a
  failed [...] fetch shouldn't break the whole page," one level up from
  where the roadmap first said it.
- **Index audit (migration `0004`), and a real bug it caught along the
  way.** Added the two foreign keys that had no index at all
  (`order_items.product_id`, `shops.address_id`), added indexes on
  columns that are filtered/sorted on a hot path but weren't indexed
  (`orders.status`, `profiles.role`, `products.created_at`), and
  replaced the single-column indexes on `orders.user_id`/`orders.shop_id`
  with composite `(user_id, created_at)` / `(shop_id, created_at)`
  indexes, since order history and the Shop Dashboard's order list both
  do exactly "WHERE X = ? ORDER BY created_at DESC" - one composite
  index serves the filter and the sort together instead of a
  single-column index needing a separate sort step as data grows.
  Writing this pass also surfaced a real, unrelated bug while reviewing
  `schemas/order.py`: `OrderStatusUpdate` was defined **twice** -
  harmless here since both definitions were identical, but dead
  copy-paste code that `ruff` (also new this phase) now catches for free.
- **Dependency vulnerability scan found real CVEs, not hypothetical
  ones.** `pip-audit` flagged 15 known vulnerabilities across `pyjwt`,
  `python-dotenv`, and `starlette` (a transitive dependency via
  `fastapi`). `pyjwt` and `python-dotenv` were straightforward bumps.
  `starlette` was not: its patched line is a new major version (1.x),
  and testing it against this project's pinned `fastapi` broke route
  introspection (Starlette's internal route representation changed
  shape) - meaning 1.x isn't the version fastapi's own maintainers are
  currently pairing it with. Rather than force an upgrade that trades a
  known, low-severity issue for an unvalidated compatibility risk, we
  pinned `starlette` one step ahead of fastapi's own resolution (closing
  5 of 6 flagged issues) and explicitly tracked the rest - see the
  comment above the pin in `requirements.txt` and the `--ignore-vuln`
  flags (with the same reasoning) in `../.github/workflows/ci.yml`. This
  is meant as an honest example of what "hardening" actually looks like:
  not blindly bumping every version pip-audit flags, but verifying each
  one and being explicit about what's fixed versus what's a tracked,
  understood trade-off.
- **`ruff` (new) - a small, high-signal rule set** (unused
  imports/undefined names/import ordering only, not opinionated style
  rules) closing out Phase 0's other never-finished promise: "lint" on
  every push. Deliberately narrow for a first-ever lint pass on this
  codebase - better to ship something actually enforced than a strict
  config someone disables in frustration two weeks from now.
- **`scripts/backup_restore_check.sh` (new).** Supabase already takes
  automatic backups - this doesn't replace that, and can't reach your
  actual Supabase project from a sandboxed environment. What it does is
  give you a repeatable way to prove a backup is actually *restorable*:
  `pg_dump` your real database, spin up a throwaway local Postgres in
  Docker, restore the dump into it, and sanity-check row counts. "A
  backup you've never restored isn't a backup," per the roadmap's own
  words - this makes that a five-minute check instead of a leap of
  faith.
- **CORS now accepts multiple origins.** `FRONTEND_ORIGIN` is
  comma-separated (`core/config.py`'s `cors_origins` property splits and
  trims it) so a staging frontend and a production frontend can both be
  listed without a code change - still never a bare `"*"`.

## Why it's built this way (Phases 1-6, still relevant)

- **Design correction, carried over from Phase 5: `POST /shops` was
  never actually "any logged-in customer can create a shop."** An
  earlier draft of this README described that as the intended design;
  the code was corrected before Phase 5 shipped (see `shops.py` -
  `create_shop` requires `role="shop_owner"` or `"admin"`, same as every
  `/dashboard/*` endpoint) but the README paragraph describing the old
  behavior never got updated until Phase 6. Worth flagging because it's
  exactly the kind of drift the Admin Panel exists to close the loop on:
  it makes "who becomes a seller" a real, auditable decision instead of
  a leftover TODO.
- **`admin.py` requires `role="admin"` specifically - not
  `"shop_owner", "admin"`.** Unlike the Shop Dashboard (scoped to "your
  own shops"), nothing in this router is scoped to the caller at all -
  it's full read/write access to every user and every shop on the
  platform. That's exactly the roadmap's own warning: "admin routes are
  the highest-value target for privilege escalation bugs - test role
  checks here harder than anywhere else."
- **An admin can never change their own role via the API.**
  `update_user_role` explicitly 400s if `user_id == the calling admin's
  own id`. This is a lockout guard, not a trust issue: if the only admin
  account demoted itself - even by an intended-for-someone-else misclick
  - there'd be no way to undo it from the UI, only by going around it
  with `scripts/promote_user.py` directly against the database. Forcing
  that path for your *own* role keeps it a deliberate, out-of-band act.
- **Every admin action is logged in the SAME transaction as the change
  itself** (`_record_audit` adds the `AuditLog` row to the session
  *before* `db.commit()` - one commit does both). This is deliberate:
  logging in a second, separate transaction after the fact would leave a
  window where a crash between the two commits means an action happened
  but was silently never recorded - which defeats the entire point of
  an audit trail.
- **`GET /admin/shops` reuses the existing `Shop.is_active` flag** for
  moderation - no new "approval status" column needed. The `Shop` model
  already anticipated this back in Phase 1/5 (`"Admin can deactivate a
  shop (Phase 6) without deleting its data"`), so deactivating a
  problem shop is the same flag a shop owner already used for their own
  shop, just reachable now for *any* shop, by an admin, with the
  customer-facing caches (`shops:list`, `shop:{id}`, `categories:list`)
  invalidated the same way `shop_dashboard.py` already does.
- **`GET /admin/metrics` runs ~8 small, independent COUNT/SUM queries**
  rather than one clever joined query. Profiles, shops, products, and
  orders aren't related by any single key that would make a combined
  query meaningful without fan-out silently multiplying some of the
  counts (e.g. joining shops to orders multiplies the shop count by
  however many orders each shop has). At this scale, several obviously-
  correct indexed queries beat one query that's subtly wrong.
- **GMV uses the exact same rule as the Shop Dashboard's own revenue
  number**: sum of `total_amount` on `status="confirmed"` orders only -
  a `pending` order hasn't been paid for, and a `payment_failed` one
  never will be, so neither counts as platform sales.
- **`shop_dashboard.py` - every mutating endpoint relies on one function:
  `_user_owns_shop(shop, user)`.** Deliberately pulled out as a
  standalone function so it's unit-testable without a live database - a
  shop owner correctly gets denied on another shop's products/orders, an
  admin is allowed everywhere, and a `None` shop (bad ID) is never
  treated as owned.
- **Applying to sell is self-service; the shop listing going live is
  not.** `POST /shops` accepts any authenticated, non-suspended account
  and promotes a plain `customer` to `shop_owner` in the same
  transaction as their application (no separate admin step to unlock
  the Shop Dashboard). What's still admin-gated is the **shop itself**:
  every new shop is created `approval_status="pending"` and
  `is_active=False`, invisible on the storefront until an admin approves
  it from the Manage Shops queue - so `/dashboard/*` (managing products,
  orders, etc.) only opens up once that specific shop is approved, via
  `_require_approved_shop`, regardless of the owner's role.
- **`shop_id` in request bodies is never trusted by itself.** `POST
  /dashboard/products` takes a `shop_id`, but the endpoint still looks up
  that shop and checks ownership before creating anything - a malicious
  or buggy client sending someone else's shop ID gets a 403, not a
  successful write into a shop they don't own.
- **`DELETE /dashboard/products/{id}` deactivates, never hard-deletes.**
  A real `DELETE` would violate the `RESTRICT` foreign key from
  `order_items` the moment anyone's ever bought the product.
- **Order status transitions are a fixed forward-only map**
  (see `core/order_status.py`). Payments are direct customer -> shop, so
  orders start at `confirmed`; payment state lives on `payments`
  (`unpaid -> submitted -> paid`, confirmed by the shop). `cancelled` is a
  separate action that releases stock.
- **Cache invalidation is wired up properly.** `core/cache.py`'s
  `invalidate()` helper is called by every dashboard write that changes
  customer-visible data - a price or stock change is visible to shoppers
  immediately, not up to a minute later.
- **`GET /dashboard/summary` uses one `GROUP BY` query with a `FILTER`
  clause** rather than looping and querying once per shop.

## What's next (Phase 8)

Launch & beyond - custom domain + SSL, a staging environment kept alive
permanently, and then watching real usage to decide what actually needs
scaling, rather than pre-optimizing for load that doesn't exist yet.


## Reviews & ratings (migration 0021)

Run `alembic upgrade head`. Customers with a delivered/picked-up order can
rate (1-5 stars) and review products and shops; reviews are public, one per
customer per product/shop (editable). Shop owners/managers manage them under
`/dashboard/reviews` (reply, hide/unhide). `products.rating_avg/rating_count`
and `shops.rating/rating_count` are recomputed on every change
(`app/core/reviews.py`). Routers: `routers/reviews.py` (public + customer),
`routers/shop_reviews.py` (owner).

## Recommendations (migration 0022)

Item-to-item "customers also bought" engine: nightly batch build + indexed
request-time serving, with an offline quality gate, rollback, opt-out,
experiment holdout and an admin dashboard. Full architecture, thresholds and
runbook: [`docs/recommendations.md`](docs/recommendations.md).

```bash
alembic upgrade head                                   # adds the tables + profiles.personalization_opt_out
pip install -r requirements-reco.txt                   # numpy/scipy, needed by the job only
python -m scripts.seed_reco_demo                       # (dev) synthetic shoppers
python -m scripts.build_recommendations                # build, evaluate, promote if good
python -m scripts.build_recommendations --rollback     # emergency: previous model
```
Schedule the build nightly (02:30 IST) and monitor `GET /health/recommendations`.
Kill switch: `RECO_ENABLED=false`.


## Hardening pass 2 (migration 0023)

Run `alembic upgrade head` (adds `pg_trgm` + search indexes) and set the new env vars below on your host.

- **Cart quantities are validated** (`1..99` per line, `0` removes) at the API *and* re-checked at checkout — a negative quantity previously passed the stock guard and could add stock / make a negative total.
- **Checkout idempotency is atomic** (`SET NX` lock in `core/idempotency.py`): simultaneous retries with the same key run the checkout once; a duplicate waits for the first result, or gets `409` if it takes >10 s.
- **Stale orders expire** (`core/order_expiry.py`, `python -m scripts.expire_unpaid_orders`, every ~15 min): a still-unpaid UPI order after `ORDER_UNPAID_UPI_EXPIRY_MINUTES` (120), or any order the shop never started after `ORDER_UNACTED_EXPIRY_HOURS` (24), is cancelled and its stock released. Orders with a *submitted*/*paid* payment, or that the shop already started, are never auto-cancelled. Scheduled by the `expire-orders` job in `.github/workflows/ci.yml` (needs the repo secrets), or use your host's cron.
- **`/health`** returns `ok`/`error` only; details go to the logs.
- **Per-IP rate limiting behind a proxy:** set `TRUSTED_PROXY_COUNT` (1 on Railway/Render/Fly/Heroku). See `core/client_ip.py`. Left at `0`, the `X-Forwarded-For` header is ignored.
- **Search:** user text is escaped (no accidental `%`/`_` wildcards), typo-tolerant name matching via `pg_trgm`, and `limit`/`offset` pagination on `/products` and `/shops`. No full-text stemming yet.
- Removed the dead `routers/webhooks.py`; bumped `pyjwt` to 2.15.1 (14 new advisories on 2.13.0); added `pyproject.toml` (ruff: unused/undefined names only).
- **Tests:** `tests/test_integration_fixes.py` runs against real Postgres + Redis (skips when unavailable). CI now provides both.


## Notifications & order history (migration 0024)

**Order history** (`order_events`): every order, payment and return change appends a row — what happened, who did it (`actor_id` + `actor_role`), from/to status, a note, and metadata such as the delivery-proof photo or a UTR. A database trigger rejects edits (the only allowed change is `actor_id` → NULL when an account is deleted, so the record survives and still says "a manager"). Everything goes through `core/order_events.order_changed()`, called before `commit()` so the history commits atomically with the change. Views: customer `GET /orders/{id}/timeline` (staff shown only as "The shop"), shop `GET /dashboard/orders/{id}/timeline` (names + roles), admin `GET /admin/orders/{id}/timeline`. Existing orders were back-filled with a starting entry.

**Notifications**: each event notifies the right people (`core/notification_templates.py` has all the wording): the customer gets an order receipt, step updates, payment/return outcomes and cancellations; the shop owner and managers get new orders, payments to confirm, cancellations/expiries and return requests. Each notification is an in-app row (the bell: `GET /notifications`, `/notifications/unread-count`, `POST /notifications/{id}/read`, `/notifications/read-all`) plus, if the user has an email and hasn't turned it off (My Account → Settings), a queued email.

**Reliability design**
- Notification rows and queued emails are written in the *same transaction* as the order change (transactional outbox): never an email for a rolled-back order, never an order whose "new order" alert was lost.
- Notifying runs in a savepoint: a bug in a template can't block an order — it's logged and the order still goes through (history is still recorded).
- Emails are delivered by a worker with retries (1 → 2 → 4 → 8 min, `NOTIFICATION_MAX_ATTEMPTS`, then marked `failed` with the error kept). Rows are claimed with `FOR UPDATE SKIP LOCKED` + a lease, so several workers never double-send and a crashed worker's rows are retried.
- The worker runs **inside the API process** by default (`NOTIFICATION_WORKER_ENABLED=true`). If your backend host is serverless/ephemeral, turn that off and run `python -m scripts.send_notifications` from cron every minute (or `--loop` as its own worker).

**Choose an email provider** (`EMAIL_PROVIDER`): `console` (default — logs only, sends nothing), `resend` (`RESEND_API_KEY`), or `smtp` (Brevo/SES/etc.). Use an `EMAIL_FROM` on a domain you've verified with the provider (SPF/DKIM), or messages will land in spam. Check failures with: `SELECT status, last_error, count(*) FROM notification_outbox GROUP BY 1, 2;`

Not built yet: SMS/WhatsApp/web push (the outbox has a `channel` column ready for them), reminders to shops about unconfirmed orders, per-event notification preferences.


## Shop profile, delivery pricing, ETA & time slots (migration 0025)

**Shop profile** — new shop fields: `contact_phone` (required to apply; can't be cleared later), `description`, `opening_hours`, `timezone`, and a vacation switch (`temporarily_closed` + optional `closed_until` + `closed_message`). Owners edit these in the dashboard's **Store settings** tab (`PUT /dashboard/shops/{id}`); customers see them on the store page and in `GET /shops`, `GET /shops/{id}` (including a computed `open_info`: `{is_open, state, opens_at, closes_at, message}`).

**Opening hours** (`core/shop_hours.py`) — a weekly schedule of up to 3 ranges per day in the shop's timezone; `"24:00"` means midnight; a closing time at/before the opening time runs past midnight; a day with no ranges is closed. **`opening_hours = NULL` means "not set" = always open**, so shops that existed before this feature behave exactly as before until their owner sets hours. Vacation mode overrides everything and reopens by itself at `closed_until`. `open_info` in shop responses is cached up to 60 s with the rest of the response; the checkout always re-checks live.

**Delivery pricing** (delivery orders only — pickup never pays a fee and has no minimum): `delivery_fee`, `free_delivery_above` (subtotal at/above it ⇒ fee waived), `min_order_amount` (items subtotal, before the fee). Orders now store `subtotal_amount` + `delivery_fee` (+ `total_amount` = their sum = what the customer pays the shop, also the payment amount), fixed at placement — changing a shop's fee later never alters a past order. Returns refund item prices only, not the delivery fee.

**ETA** — every order gets `eta_at`: placement + `prep_time_minutes` (+ `delivery_time_minutes` for delivery). Shops can move it with `PATCH /dashboard/orders/{id}/eta` (recorded in the order history as `eta_changed`, customer notified).

**Time slots** (opt-in per shop, needs opening hours): slots of `slot_length_minutes`, aligned to the shop's clock, fully inside opening hours and outside vacations, no sooner than prep (+ delivery) time from now, up to `slot_days_ahead` calendar days, at most `slot_capacity` non-cancelled orders each. Booking a slot is serialised with a Postgres advisory lock so two customers can't both take the last place (tested with concurrent checkouts). A shop that's closed right now still accepts orders **for a slot**; a vacationing shop doesn't. A cancelled order frees its place.

**One rule-set, two entry points** — `core/shop_plan.plan_shop_order()` decides open/closed, minimum, fee, slot and ETA. `POST /orders/quote` (used live by the checkout page) returns every problem; `POST /orders` (real checkout) refuses on the first one, using the same code. Checkout also now refuses shops that are unlisted or not approved.

Not built yet: ordering open shops first in listings, holiday-specific hours (use the vacation switch), per-distance delivery fees, a delivery fee for pickup-and-collect-later orders.


## Product pricing, units, SKU/barcode & low-stock alerts (migration 0026)

**Price vs MRP** — `price` is always the SELLING price (what's charged, what checkout uses). `mrp` is optional: when it's above the price, customers see it struck through with "X% off" (`discount_percent`, only when it rounds to ≥ 1%). `mrp` must be ≥ `price` (selling above MRP is illegal for packaged goods in India) — enforced by the API, and by a database check. Orders snapshot `mrp` and the pack size on each line, so editing a product later never changes what an old order shows; order detail also returns `savings_amount`.

**Pack size** — `unit_value` + `unit` (g, kg, ml, l, pcs, pack, dozen), both or neither → `unit_label` ("500 g", "1 L"). For weight/volume packs a comparison price is computed (`unit_price_label`, e.g. "₹8 / 100 g"), shown on the product page.

**SKU & barcode** — owner-only fields (never in public responses). SKU: letters/numbers/`. _ - /`, ≤ 40 chars, unique per shop case-insensitively. Barcode: EAN-8/UPC-A/EAN-13/GTIN-14 with the **check digit verified** (catches typos/bad scans), unique per shop. Different shops may reuse the same value. Duplicates return 409 with a clear message. `GET /dashboard/products?q=` searches name, SKU and an exact barcode (what a scanner "types").

**Input validation that didn't exist before** — price must be > 0, stock ≥ 0 (API + a DB check, added `NOT VALID` so legacy negative rows don't block the migration but no new ones can be written).

**Low-stock alerts** (`core/stock_alerts.py`) — a product is "low" at/below its `low_stock_threshold` (else the shop's default `shops.low_stock_threshold`, 5) and "out" at 0. The owner and managers get a bell + email notification **once when a product enters low, and once when it sells out** — not on every sale. Restocking re-arms it silently. The state change is a compare-and-set, so simultaneous sales still send exactly one alert (tested). Edits made by the owner themselves update the state without notifying them. `GET /dashboard/products?stock=low|out` and `GET /dashboard/products/stock-summary` power the Inventory tab and the dashboard banner.

Not built yet: barcode scanning with the phone camera (the site's Permissions-Policy currently blocks the camera), bulk CSV import/export of prices and stock, price history, per-variant MRP editing in bulk, GST rates/HSN codes (planned with invoices).


## Customer support: reports, disputes & admin resolution (migration 0028)

Customers can report a problem; shops reply once; admins resolve what is escalated. **Returns are a separate feature and are unchanged** — a rejected return does *not* flow into this.

**What can be reported** (`POST /support/cases`, reasons are fixed lists from `GET /support/options`)
- `order_problem` / `payment_problem` — about one of the customer's orders. The shop replies first. Reportable while the order is open and for `SUPPORT_REPORT_WINDOW_DAYS` (3) after delivery/pickup (or after cancellation). **One unresolved report per order** (also a partial unique index in the database).
- `shop_report` — about a shop; `general` — an app/account issue. Both go **straight to admin**. For a shop report the shop is notified that a report exists, *without details*, and never sees it in its list.

**Flow (order/payment problems)**
1. Customer files it (text + up to 5 photos) → shop owner and managers are notified in-app.
2. The shop sends **one** structured reply — agree to fix / offer / disagree (with explanation and photos) — **or** asks the customer for more information **once** (the customer answers, then the shop replies).
3. The customer **accepts** or **escalates to admin** — escalation is allowed at any time while the report is open.
4. No shop reply within `SUPPORT_SHOP_REPLY_HOURS` (48) → flagged "overdue" to admin. Customer silent for `SUPPORT_AUTO_CLOSE_DAYS` (3) after a shop reply or info request → closes automatically.

**Admin** (`/admin/support/*`)
- **Rule**: for the customer / for the shop / no fault, with a note shown to **both** sides. When ruling for the customer an admin may also **order a refund or resend by a deadline**; the case waits (`action_pending`) until the shop (or an admin) confirms it. The platform never holds the money, so this is an instruction, not a transfer. A missed deadline only **alerts admin** — no automatic penalty.
- **Review** shop reports / general issues: the reporter only ever sees "action taken" or "no action needed".
- **Act on the shop**: warn (shop sees the note), hide (same `is_active` switch as Manage Shops), or suspend the owner's account (the shop stays visible unless also hidden).
- **Flag customers**: after 3 disputes ruled against a customer in 60 days the system *suggests* a flag and notifies admins; an admin confirms. A flag is informational only — it restricts nothing by itself.
- Internal notes are admin-only and never serialised for customers or shops (`core/support_view.py` decides who sees what on the server). Every admin action is audit-logged in the same transaction.

**Notifications** are **in-app only** (no email) via the existing bell. Case history is append-only (`support_case_events`, UPDATEs rejected by a trigger) and key steps are mirrored onto the order timeline as evidence.

**Scheduled job** — `python -m scripts.sweep_support` (flags overdue, auto-closes idle cases, alerts on late admin-ordered actions). It runs as a second step of the existing every-15-minutes `expire-orders` job in `.github/workflows/ci.yml`; use your host's cron if you prefer.

Tunables: `SUPPORT_REPORT_WINDOW_DAYS`, `SUPPORT_SHOP_REPLY_HOURS`, `SUPPORT_AUTO_CLOSE_DAYS`, `SUPPORT_MAX_PHOTOS`. Tests: `tests/test_support_rules.py` (pure) and `tests/test_integration_support.py` (end to end, needs Postgres + Redis).
