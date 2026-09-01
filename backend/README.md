# LocalMart Backend (FastAPI)

## What exists right now (Phase 0 through 5)

```
app/
  main.py                # app entrypoint, CORS setup, router registration
  core/
    config.py, db.py, redis_client.py, security.py
    cache.py                  # now also has invalidate() (new)
    utils.py, cart.py, idempotency.py
  models/
    base.py, profile.py, address.py, shop.py, product.py
    order.py, order_item.py, payment.py
  schemas/
    profile.py, category.py, address.py
    shop.py (added ShopCreate/ShopUpdate)
    product.py (added ProductCreate/ProductUpdate)
    order.py (added DashboardOrderOut/OrderStatusUpdate)
  routers/
    health.py, auth.py, categories.py, products.py
    cart.py, addresses.py, webhooks.py
    shops.py (added POST /shops — "become a seller")
    orders.py (unchanged this phase)
    shop_dashboard.py (new)        # the whole Shop Dashboard API
migrations/                 # Alembic (0001, 0002 — no new migration this phase)
scripts/
  seed.py
```

## Setup

No new env vars, no new migration — this phase is pure application logic
on top of tables that already existed. Same setup as Phase 4.

## Try the new endpoints

```bash
# Become a seller (any logged-in user can do this):
curl -X POST http://localhost:8000/shops \
  -H "Authorization: Bearer YOUR_TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "My Shop", "category": "Groceries"}'

# See your shops / add a product / see incoming orders / see revenue:
curl http://localhost:8000/dashboard/shops -H "Authorization: Bearer YOUR_TOKEN"
curl http://localhost:8000/dashboard/orders -H "Authorization: Bearer YOUR_TOKEN"
curl http://localhost:8000/dashboard/summary -H "Authorization: Bearer YOUR_TOKEN"
```

## Why it's built this way

- **`POST /shops` (in `shops.py`) IS the "become a seller" action.** Any
  logged-in customer can create a shop; doing so elevates their `role`
  from `customer` to `shop_owner` in the same transaction. There's no
  separate application/approval flow yet — a natural fit for a future
  admin feature (approving new shops before they go live).
- **`shop_dashboard.py` — every mutating endpoint relies on one function:
  `_user_owns_shop(shop, user)`.** It's deliberately pulled out as a
  standalone function, not inlined, specifically so it's unit-testable
  without a live database. I tested it directly: a shop owner correctly
  gets denied on another shop's products/orders, an admin is allowed
  everywhere, and a `None` shop (bad ID) is never treated as owned. This
  is the exact check the roadmap called out as worth testing explicitly —
  a shop owner hitting another shop's data must get a clean 403, never a
  leak.
- **Design correction (5.2): selling is NOT self-service.** An earlier
  version of this phase let any customer become a shop_owner just by
  creating a shop — that turned out to be the wrong call. Every
  `/dashboard/*` endpoint and `POST /shops` now require
  `role="shop_owner"` or `"admin"` via `require_role(...)`, and there is
  **no endpoint that lets an account promote itself.** Becoming a
  shop_owner is an explicit action taken on the account from outside —
  today that means `scripts/promote_user.py` (see below), and once Phase
  6 ships, a real "approve this seller" action in the Admin Panel. This
  matches how real marketplaces actually onboard sellers: vetted, not
  self-granted.
- **`scripts/promote_user.py`** — the stop-gap for turning a customer
  into a shop_owner until the Admin Panel exists:
  `python -m scripts.promote_user someone@example.com shop_owner`. The
  target account must have logged in at least once already (a profile
  row is only created on first authenticated request).
- **`shop_id` in request bodies is never trusted by itself.** `POST
  /dashboard/products` takes a `shop_id`, but the endpoint still looks up
  that shop and checks ownership before creating anything — a malicious
  or buggy client sending someone else's shop ID gets a 403, not a
  successful write into a shop they don't own.
- **`DELETE /dashboard/products/{id}` deactivates, never hard-deletes.**
  A real `DELETE` would violate the `RESTRICT` foreign key from
  `order_items` the moment anyone's ever bought the product — and even
  before that, sellers generally want discontinued products to stay in
  their history, not vanish. This is exactly the `is_active` flag the
  rest of the catalog already respects.
- **Order status transitions are a fixed forward-only map**
  (`confirmed → shipped/cancelled`, `shipped → delivered`) —
  `pending → confirmed/payment_failed` is deliberately absent from that
  map, since only Stripe's webhook is allowed to make that call (only
  Stripe actually knows if the payment succeeded).
- **Cache invalidation, finally wired up properly.** Phase 2 mentioned
  "invalidate on price/stock update" as a TODO — `core/cache.py` now has
  an `invalidate()` helper, and every dashboard write that changes
  customer-visible data (`update_product`, `deactivate_product`,
  `create_shop`, `update_my_shop`) calls it. A price or stock change is
  now visible to shoppers immediately, not up to a minute later.
- **`GET /dashboard/summary` uses one `GROUP BY` query with a `FILTER`
  clause** (`func.count(...).filter(Order.status == "confirmed")`) rather
  than looping and querying once per shop — the kind of query worth
  writing well upfront, since an N+1 pattern here would scale badly the
  moment someone owns several shops.

## What's next (Phase 6)

Admin Panel — shop approvals, user management, and platform-wide metrics, plus an audit trail for admin actions.
