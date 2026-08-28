# LocalMart — Steps 0–3: Foundations, Auth, Browse, Cart & Checkout

Step 0 proved the wiring. Step 1 added authentication. Step 2 added
Landing/Search/Product Detail. **Step 3 adds Cart & Checkout — the
transactional core of the whole platform.** This is the phase where
correctness matters more than speed: stock can't oversell, payments can't
double-charge, and a cart spanning multiple shops has to split correctly
into separate orders per shop.

## Platform model (worth restating)

LocalMart is a **platform**, not a seller — shops own their own listings
via the Shop Dashboard (Phase 5). This shows up concretely here: checkout
creates **one Order per shop** in the cart, never one combined order that
blends two different sellers' items together.

## What you need before running this

1. A free **Supabase** project → https://supabase.com
2. A free **Upstash Redis** database → https://upstash.com
3. A free **Stripe** account (test mode) → https://dashboard.stripe.com
4. The **Stripe CLI** installed → https://docs.stripe.com/stripe-cli (for local webhook testing)

## Running it locally

Open **three** terminals this phase (one more than before, for Stripe's webhook forwarding).

**Terminal 1 — Stripe webhook forwarding:**
```bash
stripe login
stripe listen --forward-to localhost:8000/webhooks/stripe
```
Copy the `whsec_...` secret it prints — you'll need it in the backend's `.env`.

**Terminal 2 — backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # fill in DATABASE_URL, REDIS_URL, SUPABASE_URL, SUPABASE_JWT_SECRET,
                           # STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET (from Terminal 1)
alembic upgrade head      # adds orders / order_items / payments tables
python -m scripts.seed    # only if you haven't already
uvicorn app.main:app --reload --port 8000
```

**Terminal 3 — frontend:**
```bash
cd frontend
npm install
cp .env.local.example .env.local   # add NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY too
npm run dev
```

## Verifying this step worked

1. Log in, browse to any product, click **Add to cart**.
2. Open **Cart** (header) — confirm quantity/remove controls work.
3. **Proceed to checkout**, enter a delivery address, continue to payment.
4. Pay with Stripe's test card **4242 4242 4242 4242** (any future expiry, any CVC).
5. You should see "Payment successful!" on the page, AND see the webhook event logged in Terminal 1 and the backend's Terminal 2 logs.
6. In Supabase's Table Editor: `orders.status` should be `confirmed`, and the purchased product's `stock_qty` should be reduced by the quantity bought.

**Try the interesting case too:** add products from two different shops to your cart (e.g. something from Fresh Valley Groceries AND something from TechHub Electronics) and check out together — you should end up with 2 separate rows in the `orders` table, one per shop, both linked to the same Stripe payment.

## Folder-specific details

- `backend/README.md` — backend structure and setup, explained
- `frontend/README.md` — frontend structure and setup, explained

## Next step (Phase 4)

Post-purchase: order history/tracking page, and a real address book (replacing the free-text delivery address field from this phase).
