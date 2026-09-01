# LocalMart — Steps 0–5: Foundations through Shop Dashboard

Step 0 proved the wiring. Step 1 added auth. Step 2 added browsing. Step 3
added cart & checkout. Step 4 added order history/tracking and addresses.
Step 5 added the Shop Dashboard.

**Design correction (5.2): selling is not self-service.** The first
version of Phase 5 let any customer become a shop_owner just by creating
a shop from the "Sell" link. That was the wrong call for a real
marketplace — sellers should be vetted, not self-granted. Now:

- A plain customer account **cannot** create a shop or reach the Shop
  Dashboard at all — every relevant endpoint requires `role="shop_owner"`
  or `"admin"`, enforced on the backend.
- The "Sell" link in the header **only appears** for accounts that
  already have that role.
- Becoming a shop_owner is an explicit action taken from outside the
  account itself — today that's `backend/scripts/promote_user.py`; once
  Phase 6 ships, it becomes a real "approve this seller" action in the
  Admin Panel.

## What you need before running this

Same as Phase 4/5 — no new services, no new migration.

## Running it locally

Same three-terminal setup as before — see the folder READMEs.

## Verifying this step worked

1. Log in as a plain customer — confirm **"Sell" does not appear** in the header.
2. Try navigating directly to `/shop/dashboard` anyway — confirm you see a plain "Selling isn't available for your account yet" message, not an error or a dashboard UI.
3. From `backend/`, run:
   ```bash
   python -m scripts.promote_user your-email@example.com shop_owner
   ```
4. Refresh — "Sell" now appears, and the dashboard shows "Create your shop."
5. Create a shop, add a product, and confirm the full seller flow from Phase 5's original testing steps still works (buy as a different account, see the order appear in the dashboard, mark it shipped, check the summary).

## Folder-specific details

- `backend/README.md` — what changed and why
- `frontend/README.md` — what changed and why

## Next step (Phase 6)

Admin Panel — approving new sellers with a real UI (replacing the
promotion script), user management, and platform-wide metrics, with every
admin action logged for audit purposes.
