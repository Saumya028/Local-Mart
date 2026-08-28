# LocalMart Frontend (Next.js + Tailwind)

## What exists right now (Phase 0 + 1 + 2 + 3)

```
app/
  layout.tsx           # root shell — renders <Header/> on every page
  page.tsx              # Landing page: categories + shops, real data
  debug/page.tsx          # old Phase 0 connection check
  search/page.tsx           # search results page
  product/[id]/page.tsx      # product detail page
  cart/page.tsx                # cart view/edit page (new)
  checkout/page.tsx             # address + Stripe payment (new)
  login/page.tsx                  # signup/login form
  globals.css
lib/
  supabaseClient.ts      # shared Supabase browser client
  apiClient.ts             # fetch wrapper that attaches the auth token
components/
  Header.tsx              # site header on every page (now with a Cart link)
  AuthStatus.tsx            # logged-in state, calls backend /auth/me
  AddToCartButton.tsx        # the one interactive piece on Product Detail (new)
```

## Setup

1. **Install dependencies**: `npm install` (adds `@stripe/stripe-js` and `@stripe/react-stripe-js` this phase)
2. **Env**: `cp .env.local.example .env.local`, fill in the usual vars plus (new) `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` — from the same Stripe Dashboard page as the backend's secret key (this one starts `pk_test_`, safe to expose in the browser).
3. **Make sure the backend is fully running** — including `stripe listen --forward-to localhost:8000/webhooks/stripe` in its own terminal (see backend README) — or payments will appear to hang forever waiting for confirmation.
4. **Run**: `npm run dev`

## Try the full flow

1. Log in (or sign up) if you haven't already.
2. Go to a product page, click **Add to cart**.
3. Click **Cart** in the header — adjust quantity, or add a second product from a different shop (this tests the multi-vendor split at checkout).
4. Click **Proceed to checkout**, enter any delivery address, continue.
5. On the payment step, use Stripe's test card: **4242 4242 4242 4242**, any future expiry date, any 3-digit CVC.
6. You should see "Payment successful!" — and in the terminal running `stripe listen`, you'll see the webhook event come through and your backend log the confirmation.
7. Check Supabase's Table Editor → `orders` — status should now say `confirmed`, and `products.stock_qty` for what you bought should be reduced.

## Why it's built this way

- **Auth (Phase 1)** talks to Supabase directly from the browser. **Landing, Search, Product Detail (Phase 2)** are Server Components fetching data server-side.
- **`AddToCartButton.tsx` is a small, isolated Client Component** — the rest of the Product Detail page stays a Server Component. Pulling out just the interactive piece, rather than making the whole page client-rendered, keeps the page's data-fetching fast and simple; only the one button needs the browser's auth token.
- **`cart/page.tsx` is a full Client Component**, unlike the browsing pages — it needs the auth token for every request (this cart belongs to a specific logged-in user) and re-fetches after every quantity change, which doesn't fit the "fetch once server-side" pattern the browsing pages use.
- **`checkout/page.tsx` generates one idempotency key per page load** (`generateIdempotencyKey()`), sent as the `Idempotency-Key` header on the checkout request. If the "Continue to payment" click gets retried (slow network, accidental double-click before the button disables), the backend recognizes the same key and returns the same result instead of creating duplicate orders.
- **Stripe Elements (`<Elements>`, `<CardElement>`)** — the actual card number never touches our server or even our own frontend code directly; Stripe's own hosted iframe handles that input, and `stripe.confirmCardPayment()` talks to Stripe directly from the browser using the `client_secret` our backend generated. This is *why* it's safe to handle payments this way — sensitive card data never enters our system at all, which also keeps us out of most PCI compliance scope.
- **Payment confirmation happens via webhook, not directly in this page.** After `confirmCardPayment()` returns "succeeded", the *backend's* webhook handler is what actually marks the order confirmed — the frontend result here is just for showing the user immediate feedback. This separation matters: if someone closed the tab right after paying, the order still gets confirmed correctly because Stripe's webhook fires independently of whether anyone's watching this page.

## What's next (Phase 4)

Order history / tracking page (`/orders`), and an address book so "delivery address" becomes a saved selection instead of typing it fresh every checkout.
