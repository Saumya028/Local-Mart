# LocalMart Backend (FastAPI)

## What exists right now (Phase 0 through 6)

```
app/
  main.py                # app entrypoint, CORS setup, router registration
  core/
    config.py, db.py, redis_client.py, security.py
    cache.py, utils.py, cart.py, idempotency.py
  models/
    base.py, profile.py, address.py, shop.py, product.py
    order.py, order_item.py, payment.py
    audit_log.py (new)              # admin action trail
  schemas/
    profile.py, category.py, address.py
    shop.py, product.py
    order.py (added DashboardOrderOut/OrderStatusUpdate)
    dashboard.py
    admin.py (new)                  # AdminUserOut, RoleUpdate, AdminShopOut, ShopStatusUpdate, AuditLogOut, PlatformMetrics
  routers/
    health.py, auth.py, categories.py, products.py
    cart.py, addresses.py, webhooks.py
    shops.py, orders.py
    shop_dashboard.py               # the Shop Dashboard API
    admin.py (new)                  # the whole Admin Panel API
migrations/                 # Alembic (0001, 0002, 0003 — audit_logs table, new this phase)
scripts/
  seed.py, promote_user.py    # promote_user.py is now only for bootstrapping the first admin (see below)
```

## Setup

One new migration this phase — run it before anything else:

```bash
alembic upgrade head
```

No new env vars.

## Try the new endpoints

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

## Bootstrapping your first admin

The Admin Panel is admin-only and there's a chicken-and-egg problem: you
need an admin account to grant admin access through the UI. So
`scripts/promote_user.py` still exists, but its role has narrowed —
it's now purely the one-time bootstrap step for creating your very
first admin:

```bash
python -m scripts.promote_user your-email@example.com admin
```

Every promotion/demotion after that — including granting further admins
— happens through `PATCH /admin/users/{id}/role` (i.e. the Admin Panel
UI), which is logged to `audit_logs`; the script itself deliberately
is **not** logged, since it's a direct database operation run outside
the running application.

## Why it's built this way

- **Design correction, carried over from Phase 5: `POST /shops` was
  never actually "any logged-in customer can create a shop."** An
  earlier draft of this README described that as the intended design;
  the code was corrected before Phase 5 shipped (see `shops.py` —
  `create_shop` requires `role="shop_owner"` or `"admin"`, same as every
  `/dashboard/*` endpoint) but the README paragraph describing the old
  behavior never got updated until now. Worth flagging because it's
  exactly the kind of drift Phase 6 exists to close the loop on: the
  Admin Panel is what makes "who becomes a seller" a real, auditable
  decision instead of a leftover TODO.
- **`admin.py` requires `role="admin"` specifically — not
  `"shop_owner", "admin"`.** Unlike the Shop Dashboard (scoped to "your
  own shops"), nothing in this router is scoped to the caller at all —
  it's full read/write access to every user and every shop on the
  platform. That's exactly the roadmap's own warning: "admin routes are
  the highest-value target for privilege escalation bugs — test role
  checks here harder than anywhere else."
- **An admin can never change their own role via the API.**
  `update_user_role` explicitly 400s if `user_id == the calling admin's
  own id`. This is a lockout guard, not a trust issue: if the only admin
  account demoted itself — even by an intended-for-someone-else misclick
  — there'd be no way to undo it from the UI, only by going around it
  with `scripts/promote_user.py` directly against the database. Forcing
  that path for your *own* role keeps it a deliberate, out-of-band act.
- **Every admin action is logged in the SAME transaction as the change
  itself** (`_record_audit` adds the `AuditLog` row to the session
  *before* `db.commit()` — one commit does both). This is deliberate:
  logging in a second, separate transaction after the fact would leave a
  window where a crash between the two commits means an action happened
  but was silently never recorded — which defeats the entire point of
  an audit trail.
- **`GET /admin/shops` reuses the existing `Shop.is_active` flag** for
  moderation — no new "approval status" column needed. The `Shop` model
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
  number**: sum of `total_amount` on `status="confirmed"` orders only —
  a `pending` order hasn't been paid for, and a `payment_failed` one
  never will be, so neither counts as platform sales. Keeping this one
  rule in exactly one place (conceptually) means the per-shop revenue a
  seller sees and the platform-wide GMV an admin sees can never quietly
  disagree with each other over what "a sale" means.
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
  `/dashboard/*` endpoint and `POST /shops` require `role="shop_owner"`
  or `"admin"` via `require_role(...)`, and there is **no endpoint that
  lets an account promote itself.** Becoming a shop_owner is an explicit
  action taken on the account from outside — as of Phase 6, that's a
  real "approve this seller" action in the Admin Panel
  (`PATCH /admin/users/{id}/role`), replacing what used to be a
  one-off script for every promotion. This matches how real marketplaces
  actually onboard sellers: vetted, not self-granted.
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
  map, since only Razorpay's webhook is allowed to make that call (only
  Razorpay actually knows if the payment succeeded).
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

## What's next (Phase 7)

Production hardening pass — rate limiting on auth/checkout, a
dependency vulnerability scan, confirmed DB backups/restore, Sentry on
both frontend and backend, structured logging with request IDs, and a
pass over indexes/cache hit rates now that every phase's data model is
in place.
