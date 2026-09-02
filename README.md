# LocalMart — Steps 0–6: Foundations through Admin Panel

Step 0 proved the wiring. Step 1 added auth. Step 2 added browsing. Step 3
added cart & checkout. Step 4 added order history/tracking and addresses.
Step 5 added the Shop Dashboard. Step 6 adds the Admin Panel.

**Design correction (5.2): selling is not self-service.** The first
version of Phase 5 let any customer become a shop_owner just by
creating a shop from the "Sell" link. That was the wrong call for a real
marketplace — sellers should be vetted, not self-granted. Now:

- A plain customer account **cannot** create a shop or reach the Shop
  Dashboard at all — every relevant endpoint requires `role="shop_owner"`
  or `"admin"`, enforced on the backend.
- The "Sell" link in the header **only appears** for accounts that
  already have that role.
- Becoming a shop_owner is now a real "approve this seller" action in
  the Admin Panel, taken by an existing admin — not something an
  account can do to itself.

## What's new in Phase 6 — Admin Panel

- **User management**: search users by email, and approve/promote or
  demote any account's role (`customer` / `shop_owner` / `admin`) from
  a real UI — this replaces `scripts/promote_user.py` for day-to-day
  use. The script still exists, narrowed to one job: bootstrapping your
  very first admin account (see `backend/README.md`).
- **Shop moderation**: see every shop on the platform (not just your
  own) with its owner's email, and deactivate/reactivate any of them —
  reusing the same `is_active` flag a shop owner already toggles for
  their own shop.
- **Platform metrics**: total users, shop owners, admins, total/active
  shops, total/active products, total/confirmed orders, and GMV
  (confirmed-order revenue, platform-wide).
- **Audit trail**: every role change and shop status change made
  through the panel is logged — who did it, what changed, and when —
  written in the same database transaction as the change itself, so an
  action can never happen without being recorded (or be "recorded"
  without actually happening).
- An admin **cannot change their own role** from the panel — a
  deliberate lockout guard, not a trust issue (see `backend/README.md`
  for the reasoning).

## What you need before running this

Same services as before, plus **one new migration** (`0003`, adds
`audit_logs`) — see `backend/README.md`'s Setup section.

## Running it locally

Same three-terminal setup as before — see the folder READMEs.

## Verifying this step worked

1. Bootstrap your first admin (from `backend/`):
   ```bash
   python -m scripts.promote_user your-email@example.com admin
   ```
2. Log in as that account — confirm **"Admin" appears in the header** (and doesn't for a plain customer account).
3. In the Admin Panel's **Metrics** tab, confirm the numbers look sane (they should match what you already have seeded/tested).
4. In **Users**, search for a customer's email and promote them to `shop_owner` — confirm they can now reach `/shop/dashboard` and create a shop.
5. In **Shops**, deactivate that new shop — confirm it disappears from the public "Shops near you" list and search almost immediately (cache invalidation), then reactivate it.
6. In **Audit Log**, confirm both actions above show up, newest first, with your admin email and the before/after values.
7. Confirm a `shop_owner` (non-admin) account navigating to `/admin` directly sees the "restricted" message, not a 403 flash or the panel itself.

## Folder-specific details

- `backend/README.md` — what changed and why
- `frontend/README.md` — what changed and why

## Next step (Phase 7)

Production hardening pass — rate limiting, a secrets/CORS/dependency
audit, confirmed DB backups + a tested restore, error tracking and
structured logging, and a check of cache hit rates and indexes now that
the full feature set (Phases 0–6) is in place. Per the roadmap's own
rule, this isn't building these habits from scratch — auth tests,
ownership checks, and cache invalidation have been part of every phase
so far — it's validating them under one dedicated pass.
