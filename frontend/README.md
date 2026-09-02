# LocalMart Frontend (Next.js + Tailwind)

## What exists right now (Phase 0 through 6)

```
app/
  layout.tsx           # wraps everything in <AuthProvider>, renders <Header/>
  page.tsx, debug/, search/, product/[id]/
  cart/, checkout/, orders/, orders/[id]/, profile/
  shop/dashboard/page.tsx   # the Shop Dashboard UI
  admin/page.tsx (new)      # the whole Admin Panel UI
  login/, globals.css
lib/
  supabaseClient.ts, apiClient.ts
contexts/
  AuthContext.tsx        # shared profile/role state
components/
  Header.tsx (role-aware "Sell" AND "Admin" links, new), AuthStatus.tsx
  AddToCartButton.tsx, AddressForm.tsx
```

## Setup

No new env vars. `npm install`, `npm run dev` as before — but the
backend needs its Phase 6 migration run first (`alembic upgrade head`
in `backend/`), and you'll need an admin account to see anything under
`/admin` (see the backend README's "Bootstrapping your first admin").

## Try it — selling is NOT self-service

1. As a plain customer, notice **"Sell" doesn't appear in the header at all.**
2. Bootstrap your first admin account — from `backend/`:
   ```bash
   python -m scripts.promote_user your-email@example.com admin
   ```
3. Log out and back in (or just refresh) — **"Admin" now appears in the header.** From here on, approving new sellers happens in the UI, not a script (see below).
4. If a plain customer navigates straight to `/shop/dashboard` by URL anyway, they see a clear "Selling isn't available for your account yet" message — no dashboard UI flashes, no failed request happens, because the page checks the role it already knows *before* asking the backend anything. `/admin` behaves the same way for non-admins.

## Try the Admin Panel (once you have an admin account)

1. Click **Admin** in the header.
2. **Metrics tab** (the default view) — total users, shop owners, admins, total/active shops, total/active products, total/confirmed orders, and GMV (confirmed-orders revenue, platform-wide).
3. **Users tab** — search by email, then use the role dropdown on any row to approve a customer as a seller (`shop_owner`) or grant/revoke admin access. Granting `admin` asks for one extra confirmation, since it's a real privilege escalation. Your own row's dropdown is disabled — you can't change your own role from the UI (see the backend README for why).
4. **Shops tab** — every shop on the platform, not just ones you own, with the owner's email. **Deactivate**/**Reactivate** any shop — same `is_active` flag a shop owner already toggles for their own shop, just reachable here for any shop on the platform.
5. **Audit Log tab** — every role change and shop status change ever made through this panel, newest first, with who did it, what changed, and when.

## Try the seller flow (once promoted)

1. Click **Sell**, create your first shop (name + category).
2. On the **Products** tab, click **+ Add product**, fill in the form, save.
3. Edit the stock number inline (click into the box, change it, click away) — saved automatically on blur.
4. Click **Deactivate** on a product — hidden from customer search/browsing, but not deleted (click **Reactivate** to bring it back).
5. Switch to **Orders** — any order placed against your shop shows here with the buyer's email and a **Mark shipped/delivered/cancelled** action, depending on its current status.
6. Switch to **Summary** — confirmed order count and total revenue.
7. **To see this fully end to end**: place a real test order as a *different* logged-in account against your shop's product, complete payment, then come back to your dashboard's Orders tab and watch it appear.

## Why it's built this way

- **`app/admin/page.tsx` follows the exact same shape as `shop/dashboard/page.tsx`**: a role check from `useAuth()` gates the whole page before any `/admin/*` call ever goes out, then tabs (Metrics/Users/Shops/Audit Log) each own their own `load()`/`useState` rather than one giant shared fetch — consistent with how the rest of this codebase structures multi-tab dashboards, so there's one pattern to learn, not two.
- **Granting `admin` role asks for a native `window.confirm()` first.** Every other role change (e.g. approving a `shop_owner`) is a single dropdown selection — deliberately not this one, since handing out full admin access is a meaningfully bigger action than approving a seller, and a plain dropdown makes a misclick too easy.
- **A user's own row disables the role `<select>` entirely**, mirroring the backend's own 400 on `PATCH /admin/users/{self}/role` — the frontend never even lets you attempt the request the backend would reject anyway, the same "don't dangle a control that just errors" philosophy as hiding "Sell" from customers.
- **`AuthContext` is the one place that fetches `/auth/me`.** `AuthStatus`, the Profile page, and the Shop Dashboard all now read from one shared context, populated once and kept in sync automatically via Supabase's `onAuthStateChange` listener — logging in/out updates the Header immediately, no manual refresh needed.
- **Selling is NOT self-service** (see the backend README for the full reasoning behind this design correction). On the frontend this means: the Header only renders "Sell" when `profile.role` is `shop_owner`/`admin`, and the Shop Dashboard page checks that role **before** making any `/dashboard/*` call at all.
- **Hiding "Sell" is a UX nicety, not the real security boundary** — the backend enforces this independently via `require_role` on every relevant endpoint. Even bypassing the frontend entirely (dev tools, a stale cached page), the backend still says no.
- **`AddToCartButton.tsx` is a small, isolated Client Component** — the rest of the Product Detail page stays a Server Component; only this one button needs the browser's auth token.
- **`cart/page.tsx` is a full Client Component** — it needs the auth token for every request and re-fetches after every change, which doesn't fit the "fetch once server-side" pattern the browsing pages use.
- **`checkout/page.tsx` generates one idempotency key per page load**, sent as the `Idempotency-Key` header — a retried checkout click can't create duplicate orders.
- **Razorpay Checkout** — the card number never touches our server; Razorpay's own hosted popup (loaded from `checkout.razorpay.com`) handles it directly, using the `razorpay_order_id` + `razorpay_key_id` our backend generated.
- **Payment confirmation happens via webhook, not directly in this page** — the backend's webhook handler is the actual source of truth for order status; the frontend result is just immediate user feedback.

## About the seeded demo data

`scripts/seed.py` (Phase 2) creates a `demo-owner@localmart.dev` profile
row directly in Postgres — it was never a real Supabase Auth account, so
there's no password to log in with; it exists purely to satisfy the
`shops.owner_id` foreign key so the seeded catalog had *someone* to
belong to before real sellers existed. Now that the Shop Dashboard is
real, promote a real account with `scripts/promote_user.py` instead and
create fresh shops through the UI.

## What's next (Phase 7)

Production hardening pass — this phase is about habits already built
into the app holding up under scrutiny, not new pages: rate limiting,
CORS/secrets audit, error tracking (Sentry), structured request-ID
logging, and confirming cache hit rates and DB indexes now that the
whole feature set exists.
