# LocalMart Frontend (Next.js + Tailwind)

## What exists right now (Phase 0 through 5)

```
app/
  layout.tsx           # wraps everything in <AuthProvider>, renders <Header/>
  page.tsx, debug/, search/, product/[id]/
  cart/, checkout/, orders/, orders/[id]/, profile/
  shop/dashboard/page.tsx   # the whole Shop Dashboard UI
  login/, globals.css
lib/
  supabaseClient.ts, apiClient.ts
contexts/
  AuthContext.tsx        # shared profile/role state (new)
components/
  Header.tsx (role-aware "Sell" link), AuthStatus.tsx (now reads from context)
  AddToCartButton.tsx, AddressForm.tsx
```

## Setup

No new env vars. `npm install`, `npm run dev` as before.

## Try it — selling is NOT self-service

1. As a plain customer, notice **"Sell" doesn't appear in the header at all.**
2. Promote yourself (or a test account) to a seller — from `backend/`:
   ```bash
   python -m scripts.promote_user your-email@example.com shop_owner
   ```
3. Log out and back in (or just refresh) — "Sell" now appears, and `/shop/dashboard` shows "Create your shop."
4. If a plain customer navigates straight to `/shop/dashboard` by URL anyway, they see a clear "Selling isn't available for your account yet" message — no dashboard UI flashes, no failed request happens, because the page checks the role it already knows *before* asking the backend anything.

## Try the seller flow (once promoted)

1. Click **Sell**, create your first shop (name + category).
2. On the **Products** tab, click **+ Add product**, fill in the form, save.
3. Edit the stock number inline (click into the box, change it, click away) — saved automatically on blur.
4. Click **Deactivate** on a product — hidden from customer search/browsing, but not deleted (click **Reactivate** to bring it back).
5. Switch to **Orders** — any order placed against your shop shows here with the buyer's email and a **Mark shipped/delivered/cancelled** action, depending on its current status.
6. Switch to **Summary** — confirmed order count and total revenue.
7. **To see this fully end to end**: place a real test order as a *different* logged-in account against your shop's product, complete payment, then come back to your dashboard's Orders tab and watch it appear.

## Why it's built this way

- **`AuthContext` (new) is the one place that fetches `/auth/me`.** `AuthStatus`, the Profile page, and the Shop Dashboard all now read from one shared context, populated once and kept in sync automatically via Supabase's `onAuthStateChange` listener — logging in/out updates the Header immediately, no manual refresh needed.
- **Selling is NOT self-service** (see the backend README for the full reasoning behind this design correction). On the frontend this means: the Header only renders "Sell" when `profile.role` is `shop_owner`/`admin`, and the Shop Dashboard page checks that role **before** making any `/dashboard/*` call at all.
- **Hiding "Sell" is a UX nicety, not the real security boundary** — the backend enforces this independently via `require_role` on every relevant endpoint. Even bypassing the frontend entirely (dev tools, a stale cached page), the backend still says no.
- **`AddToCartButton.tsx` is a small, isolated Client Component** — the rest of the Product Detail page stays a Server Component; only this one button needs the browser's auth token.
- **`cart/page.tsx` is a full Client Component** — it needs the auth token for every request and re-fetches after every change, which doesn't fit the "fetch once server-side" pattern the browsing pages use.
- **`checkout/page.tsx` generates one idempotency key per page load**, sent as the `Idempotency-Key` header — a retried checkout click can't create duplicate orders.
- **Stripe Elements** — the card number never touches our server; Stripe's own hosted iframe handles it, and `stripe.confirmCardPayment()` talks to Stripe directly using the `client_secret` our backend generated.
- **Payment confirmation happens via webhook, not directly in this page** — the backend's webhook handler is the actual source of truth for order status; the frontend result is just immediate user feedback.

## About the seeded demo data

`scripts/seed.py` (Phase 2) creates a `demo-owner@localmart.dev` profile
row directly in Postgres — it was never a real Supabase Auth account, so
there's no password to log in with; it exists purely to satisfy the
`shops.owner_id` foreign key so the seeded catalog had *someone* to
belong to before real sellers existed. Now that the Shop Dashboard is
real, promote a real account with `scripts/promote_user.py` instead and
create fresh shops through the UI.

## What's next (Phase 6)

Admin Panel — the last major page: approving new sellers (replacing
`scripts/promote_user.py` with a real UI), user management, and
platform-wide metrics.
