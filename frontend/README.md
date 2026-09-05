# LocalMart Frontend (Next.js + Tailwind)

## What exists right now (Phase 0 through 7)

```
app/
  layout.tsx           # wraps everything in <AuthProvider>, renders <Header/> and <Footer/>
  page.tsx, debug/, search/, product/[id]/
  cart/, checkout/, orders/, orders/[id]/, profile/
  shop/dashboard/page.tsx   # the Shop Dashboard UI
  admin/page.tsx            # the whole Admin Panel UI
  privacy/page.tsx, terms/page.tsx (new)   # Phase 7 compliance placeholders
  error.tsx, global-error.tsx, not-found.tsx (new)   # Phase 7 error boundaries
  login/, globals.css
lib/
  supabaseClient.ts, apiClient.ts   # apiClient.ts now sends/logs a per-request X-Request-ID
contexts/
  AuthContext.tsx        # shared profile/role state
components/
  Header.tsx (role-aware "Sell" AND "Admin" links), AuthStatus.tsx
  Footer.tsx (new)        # links to Privacy/Terms
  AddToCartButton.tsx, AddressForm.tsx
instrumentation.ts, instrumentation-client.ts (new)   # Sentry, optional/no-op without a DSN
eslint.config.mjs (new)   # flat ESLint config — `next lint` was removed in Next 16
```

## Setup

`npm install`, `npm run dev` as before — but the backend needs its
Phase 7 migration run first (`alembic upgrade head` in `backend/`), and
you'll need an admin account to see anything under `/admin` (see the
backend README's "Bootstrapping your first admin").

One new optional env var: `NEXT_PUBLIC_SENTRY_DSN` — leave it blank to
run with error tracking off entirely (the default; nothing here
requires a Sentry account).

**Note on the Next.js version**: this phase upgraded Next from 14.2.13
to 16.3.4 — not a routine bump, see "What changed and why (Phase 7)"
below for why. If you're pulling this after having a local checkout
from before this phase, run `npm install` fresh rather than reusing an
old `node_modules`.

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

## Try the new hardening features (Phase 7)

1. Open any page, then any network request in DevTools — every call to
   the backend carries a fresh `X-Request-ID` header (`lib/apiClient.ts`),
   which the backend echoes straight back. If a request fails, the error
   thrown includes that ID, and `app/error.tsx` surfaces it as a
   "Reference: ..." line — the exact ID to search backend logs for.
2. Visit a URL that doesn't exist — `app/not-found.tsx` shows a plain,
   friendly 404 instead of the framework default.
3. Check response headers on any page load — `X-Content-Type-Options`,
   `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` are all set
   (`next.config.js`), deliberately without a `Content-Security-Policy`
   yet (see the comment there for why guessing at one would be worse
   than not having one).
4. Scroll to the bottom of any page — **Privacy Policy** / **Terms of
   Service** links in the new footer.

## Why it's built this way

- **The Next.js upgrade (14.2.13 → 16.3.4) was a security fix, not a
  feature bump.** `npm audit` flagged a critical + high severity CVE in
  Next 14.2.13 with no fix available in the 14.x or 15.x lines — only
  16.x. This was tested empirically before adopting it (typecheck, lint,
  full production build), not assumed safe: it turned out to break two
  things that needed fixing alongside it — see the next two points.
- **`next lint` no longer exists.** Next 16 removed the `lint` CLI
  subcommand entirely. `package.json`'s `lint` script now calls `eslint .`
  directly, using ESLint 9's flat-config format (`eslint.config.mjs`),
  fed by `eslint-config-next@16`'s own flat-config export
  (`eslint-config-next/core-web-vitals.js`) instead of the old
  `.eslintrc.json` extends-based config.
- **Sentry's client config moved from `sentry.client.config.ts` to
  `instrumentation-client.ts`.** The old file is explicitly deprecated
  by `@sentry/nextjs` for one concrete reason: it silently stops working
  under Turbopack, which is Next 16's default bundler (i.e. what
  `next build`/`next dev` already use here without any extra flag).
  `instrumentation-client.ts` is a Next.js-native convention, not a
  Sentry-specific one. Server/edge Sentry init lives in `instrumentation.ts`
  (also a Next.js-native file, not new this phase in concept — just now
  actually wired up), gated the same way as the backend's
  `core/observability.py`: nothing runs, not even importing
  `@sentry/nextjs`, unless `SENTRY_DSN`/`NEXT_PUBLIC_SENTRY_DSN` is set.
- **`app/error.tsx` and `app/global-error.tsx` are two different
  boundaries, not a duplicate.** `error.tsx` is the Next.js App Router
  convention that wraps everything rendered *inside* the root layout; if
  the layout itself throws (e.g. `AuthProvider`'s initial session check
  failing), that boundary never even mounts. `global-error.tsx` is the
  one convention that sits *above* the root layout and catches that
  case specifically — which is also why it has to render its own
  `<html>/<body>` rather than assuming the real layout is there.
- **The 10 `react-hooks/set-state-in-effect` lint warnings are a known,
  tracked gap, not silently ignored.** `eslint-config-next@16` ships a
  stricter default rule set than the version this project started on,
  and it flags this codebase's very common "fetch data in a `useEffect`,
  call `setState` on the result" pattern (used in `AuthContext`, the
  Shop Dashboard, and elsewhere) as a warning. That pattern is
  standard, working React — refactoring every instance of it to satisfy
  a newly-adopted stricter lint rule is a real but separate piece of
  work, not something to rush through inside a hardening pass. They're
  warnings, not errors, so CI still passes; revisit them deliberately
  later rather than as a side effect of this phase.
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

## What's next (Phase 8)

Launch & beyond — custom domain + SSL, a permanently-alive staging
environment, and watching real usage to decide what actually needs
scaling next, rather than pre-optimizing for load that doesn't exist yet.
