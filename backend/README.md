# LocalMart Backend (FastAPI)

## What exists right now (Phase 0 + 1 + 2 + 3)

```
app/
  main.py                # app entrypoint, CORS setup, router registration
  core/
    config.py            # reads all settings from environment variables
    db.py                 # async Postgres connection (SQLAlchemy)
    redis_client.py        # async Redis connection
    security.py             # JWT verification + get_current_user / require_role
    cache.py                  # generic cache-aside helper
    utils.py                   # parse_uuid_or_404 helper
    cart.py                     # Redis-backed cart storage (new)
    idempotency.py                # dedupes retried checkout requests (new)
  models/
    base.py, profile.py, address.py, shop.py, product.py
    order.py, order_item.py, payment.py (new)
  schemas/
    profile.py, shop.py, product.py, category.py
    order.py (new)
  routers/
    health.py, auth.py, categories.py, shops.py, products.py
    cart.py (new)                # GET/POST/PUT/DELETE cart endpoints
    orders.py (new)               # POST /orders (checkout), GET /orders/{id}
    webhooks.py (new)              # POST /webhooks/stripe
migrations/                 # Alembic (0001 core tables, 0002 orders/payments — new)
scripts/
  seed.py                   # populates demo shops/products
```

## Setup

1. **Install dependencies**: `pip install -r requirements.txt` (adds `stripe` this phase)
2. **Env**: `cp .env.example .env`, fill in the usual vars plus (new) `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` — both from your [Stripe Dashboard](https://dashboard.stripe.com) in **test mode** (free to create an account; no real card ever gets charged with test-mode keys).
3. **Migrate**: `alembic upgrade head` — adds `orders`, `order_items`, `payments` tables
4. **Seed** (if you haven't already): `python -m scripts.seed`
5. **Forward Stripe webhooks to your local server** (new, required for payment confirmation to work locally):
   ```bash
   # Install the Stripe CLI (https://docs.stripe.com/stripe-cli), then:
   stripe login
   stripe listen --forward-to localhost:8000/webhooks/stripe
   ```
   This prints a webhook signing secret starting `whsec_...` — put that in `STRIPE_WEBHOOK_SECRET`. Leave this command running in its own terminal whenever you're testing checkout locally; it's how Stripe's servers reach your machine, which they otherwise can't since `localhost` isn't publicly reachable.
6. **Run**: `uvicorn app.main:app --reload --port 8000`

## Why it's built this way

- **`core/config.py`** centralizes every environment variable in one typed object (`settings`). Nothing else reads `os.environ` directly.
- **`core/db.py` / `core/redis_client.py`** each create one shared connection pool for the app's lifetime.
- **`core/security.py`** (Phase 1):
  - Verifies the JWT Supabase issued (proves *who* the user is), but deliberately does **not** trust any role/permission claim from inside that token — role always comes from our own `profiles` table.
  - **Auth fixes (1.1/1.2):** handles both Supabase's HS256 and ES256 token schemes automatically, and tolerates small clock drift (`leeway=10`) between machines.
  - `get_current_user` auto-creates a `profiles` row on first login, defaulting to `role="customer"`.
- **`models/product.py`** has an `attributes` JSONB column — deliberately avoiding a separate NoSQL database.
- **`migrations/`** — Alembic tracks schema changes over time; never edit tables directly in the Supabase dashboard.
- **`core/cache.py`** (Phase 2) — one reusable cache-aside function; `/categories`, `/shops` (unfiltered), and `/products/{id}` are cached, search is not (queries vary too much to benefit).
- **`core/cart.py`** (Phase 3) — the cart lives entirely in Redis as a hash (`cart:{user_id}` → `{product_id: quantity}`), never in Postgres. It's ephemeral, high-write, and doesn't need the durability guarantees a real database gives you — exactly the workload Redis is for.
- **`core/idempotency.py`** — wraps checkout so a retried request (network blip right as the first attempt actually succeeded) returns the same result instead of creating a second set of orders and charging the card twice. The frontend generates one key per checkout attempt and sends it as an `Idempotency-Key` header.
- **`routers/orders.py` — the checkout flow, the most important code in this phase:**
  1. Reads the cart from Redis, but re-fetches every product's real price/stock from Postgres — **the cart's cached view is never trusted for money**.
  2. Groups cart lines by shop — one `Order` row per shop, since this is a multi-vendor marketplace (see `models/order.py`'s docstring).
  3. Reserves stock with `UPDATE products SET stock_qty = stock_qty - qty WHERE stock_qty >= qty RETURNING id` — a single atomic statement. This is what makes it race-safe: I verified this exact pattern under a simulated race (two buyers, one unit left) and it correctly lets exactly one succeed, never both, never neither. A naive "read stock, check in Python, then write" approach would have a race window here that this doesn't.
  4. Nothing is committed to Postgres until the Stripe `PaymentIntent` is *also* successfully created — if Stripe's API call fails, the whole attempt (including the stock reservation) rolls back automatically, because the session is never committed.
  5. Only creates a `"pending"` order — actual confirmation happens in the webhook, asynchronously, because that's genuinely when Stripe tells us the payment succeeded or failed, not a moment before.
- **`routers/webhooks.py`** — verifies Stripe's signature on every incoming webhook (otherwise anyone who found the URL could fake a "payment succeeded" event). On `payment_intent.succeeded`, marks the order `"confirmed"`. On `payment_intent.payment_failed`, marks it `"payment_failed"` **and restores the reserved stock** — holding onto inventory for an order that's never going to be paid for would incorrectly block other customers.
- **Search is still a plain `ILIKE` substring match**, not full-text search — unchanged trade-off from Phase 2, still fine at this scale.

## What's next (Phase 4)

Post-purchase: order history/tracking (`GET /orders`), address CRUD, and email/notification on order status change.
