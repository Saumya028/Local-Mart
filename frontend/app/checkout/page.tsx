"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import AddressForm from "@/components/AddressForm";

// crypto.randomUUID() isn't guaranteed to exist in every server runtime
// this component might briefly render under during SSR, so we fall back
// rather than risk a build-time crash on an older Node version.
function generateIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// Loads Razorpay's Checkout.js exactly once, however many times this
// function gets called — the script tag registers `window.Razorpay`
// globally, so re-injecting it on every mount would be wasteful (and
// briefly leave `window.Razorpay` undefined again while it reloads).
let razorpayScriptPromise: Promise<void> | null = null;
function loadRazorpayScript(): Promise<void> {
  if (typeof window !== "undefined" && (window as any).Razorpay) {
    return Promise.resolve();
  }
  if (!razorpayScriptPromise) {
    razorpayScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://checkout.razorpay.com/v1/checkout.js";
      script.onload = () => resolve();
      script.onerror = () => reject(new Error("Failed to load Razorpay checkout"));
      document.body.appendChild(script);
    });
  }
  return razorpayScriptPromise;
}

type Address = { id: string; label: string; line1: string; city: string; is_default: boolean };

type CartShop = {
  id: string;
  name: string;
  pickup_enabled: boolean;
  address_line1: string | null;
  city: string | null;
};

type CartItem = {
  product: { id: string; name: string; price: string; images: string[] };
  quantity: number;
  subtotal: string;
  shop: CartShop | null;
};

type CheckoutResponse = {
  orders: { id: string; shop_id: string; total_amount: string; fulfillment_type?: string }[];
  razorpay_order_id: string;
  razorpay_key_id: string;
  total_amount: string;
};

// A shop can only actually be picked up from if its owner has the
// switch on AND it has an address on file — see Shop.pickup_enabled's
// docstring on the backend. Checked in exactly this shape wherever the
// frontend decides whether to offer the option.
function shopOffersPickup(shop: CartShop | null): boolean {
  return !!shop && shop.pickup_enabled && !!shop.address_line1;
}

export default function CheckoutPage() {
  // One idempotency key for this checkout attempt, generated once when
  // the page loads and reused across retries of that SAME attempt — this
  // is what lets the backend safely dedupe a retried request instead of
  // creating a second set of orders and charging twice.
  const idempotencyKey = useMemo(() => generateIdempotencyKey(), []);

  const [cartItems, setCartItems] = useState<CartItem[]>([]);
  const [loadingCart, setLoadingCart] = useState(true);

  // Per-shop fulfillment choice — keyed by shop_id, defaulting every
  // shop to "delivery" (the only option that has always existed).
  // Cart items are already destined to become separate Order rows, one
  // per shop (see the backend Order model's docstring), so this maps
  // 1:1 onto how checkout actually splits the cart — a customer can
  // pick up from one shop in their cart while having another delivered,
  // in the same checkout.
  const [fulfillment, setFulfillment] = useState<Record<string, "delivery" | "pickup">>({});

  const [addresses, setAddresses] = useState<Address[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [loadingAddresses, setLoadingAddresses] = useState(true);

  const [checkoutResult, setCheckoutResult] = useState<CheckoutResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadCart() {
    try {
      const data: { items: CartItem[] } = await apiFetch("/cart");
      setCartItems(data.items);
      // Only ever fills in shops we haven't already got a choice for —
      // preserves whatever the person already picked if this reloads.
      setFulfillment((prev) => {
        const next = { ...prev };
        for (const item of data.items) {
          if (item.shop && !(item.shop.id in next)) next[item.shop.id] = "delivery";
        }
        return next;
      });
    } catch {
      // Cart failing to load surfaces below via the empty-state message;
      // no separate error banner needed for this one.
    } finally {
      setLoadingCart(false);
    }
  }

  async function loadAddresses() {
    try {
      const data: Address[] = await apiFetch("/addresses");
      setAddresses(data);
      const preferred = data.find((a) => a.is_default) ?? data[0];
      if (preferred) setSelectedAddressId(preferred.id);
      setShowAddForm(data.length === 0);
    } catch {
      // Likely not logged in — the address list will just show empty;
      // the "add address" form below still renders and will surface the
      // real error (e.g. "log in first") when they try to save one.
    } finally {
      setLoadingAddresses(false);
    }
  }

  useEffect(() => {
    loadCart();
    loadAddresses();
  }, []);

  // Preload Checkout.js as soon as the page mounts rather than waiting
  // until the "Continue to payment" click, so opening the Razorpay popup
  // right after `startCheckout` resolves doesn't have to wait on a slow
  // script fetch too.
  useEffect(() => {
    loadRazorpayScript().catch(() => {
      // Surfaced again (and more visibly) if openRazorpayCheckout()
      // itself fails below — no need to show an error just for a
      // background preload.
    });
  }, []);

  const shopGroups = useMemo(() => {
    const byShop = new Map<string, { shop: CartShop | null; items: CartItem[] }>();
    for (const item of cartItems) {
      const key = item.shop?.id ?? "unknown";
      if (!byShop.has(key)) byShop.set(key, { shop: item.shop, items: [] });
      byShop.get(key)!.items.push(item);
    }
    return Array.from(byShop.values());
  }, [cartItems]);

  // At least one shop set to "delivery" means the address section is
  // needed at all — an all-pickup cart never touches the address book.
  const needsAddress = shopGroups.some(
    (g) => g.shop && (fulfillment[g.shop.id] ?? "delivery") === "delivery"
  );

  async function startCheckout(e: FormEvent) {
    e.preventDefault();
    if (needsAddress && !selectedAddressId) {
      setError("Please add or select a delivery address.");
      return;
    }

    const pickupShopIds = shopGroups
      .filter((g) => g.shop && fulfillment[g.shop.id] === "pickup")
      .map((g) => g.shop!.id);

    setLoading(true);
    setError(null);
    try {
      const data: CheckoutResponse = await apiFetch("/orders", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({
          address_id: needsAddress ? selectedAddressId : null,
          pickup_shop_ids: pickupShopIds,
        }),
      });
      setCheckoutResult(data);
      await openRazorpayCheckout(data, setError);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  // Once payment either succeeds or the popup is dismissed, we send the
  // shopper straight to order tracking — confirmation itself happens via
  // POST /orders/verify-payment (called from the Razorpay handler below)
  // and/or the webhook, and that page already polls for it (see
  // app/orders/[id]/page.tsx).
  if (checkoutResult) {
    return (
      <main className="max-w-md mx-auto px-6 py-10 text-center space-y-3">
        <p className="text-lg font-semibold">Order placed — ₹{checkoutResult.total_amount}</p>
        <p className="text-sm text-gray-500">
          {error
            ? error
            : "Complete payment in the Razorpay window. We'll confirm your order as soon as payment lands."}
        </p>
        <div className="space-y-1">
          {checkoutResult.orders.map((o) => (
            <a key={o.id} href={`/orders/${o.id}`} className="block text-sm text-blue-600 underline">
              Track order #{o.id.slice(0, 8)}
              {o.fulfillment_type === "pickup" ? " (Pickup)" : ""}
            </a>
          ))}
        </div>
        {error && (
          <button
            type="button"
            onClick={() => openRazorpayCheckout(checkoutResult, setError)}
            className="text-sm text-blue-600 underline"
          >
            Retry payment
          </button>
        )}
      </main>
    );
  }

  return (
    <main className="max-w-md mx-auto px-6 py-10 space-y-4">
      <h1 className="text-2xl font-bold">Checkout</h1>

      {loadingCart || loadingAddresses ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : (
        <form onSubmit={startCheckout} className="space-y-5">
          <div className="space-y-3">
            {shopGroups.map(({ shop, items }) => {
              const choice = shop ? fulfillment[shop.id] ?? "delivery" : "delivery";
              const offersPickup = shopOffersPickup(shop);
              return (
                <div key={shop?.id ?? "unknown"} className="border rounded-md p-3 space-y-2">
                  <p className="text-sm font-medium">{shop?.name ?? "Shop"}</p>
                  <ul className="text-xs text-gray-500 space-y-0.5">
                    {items.map((item) => (
                      <li key={item.product.id}>
                        {item.quantity}× {item.product.name}
                      </li>
                    ))}
                  </ul>
                  {offersPickup && shop && (
                    <div className="flex gap-3 pt-1">
                      <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                        <input
                          type="radio"
                          name={`fulfillment-${shop.id}`}
                          checked={choice === "delivery"}
                          onChange={() => setFulfillment((prev) => ({ ...prev, [shop.id]: "delivery" }))}
                        />
                        Deliver to me
                      </label>
                      <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                        <input
                          type="radio"
                          name={`fulfillment-${shop.id}`}
                          checked={choice === "pickup"}
                          onChange={() => setFulfillment((prev) => ({ ...prev, [shop.id]: "pickup" }))}
                        />
                        Pick up from shop
                      </label>
                    </div>
                  )}
                  {choice === "pickup" && shop && (
                    <p className="text-xs text-gray-400">
                      Pickup at: {shop.address_line1}
                      {shop.city ? `, ${shop.city}` : ""}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {needsAddress && (
            <div className="space-y-2">
              <p className="text-sm font-medium">Delivery address</p>
              {addresses.map((a) => (
                <label
                  key={a.id}
                  className="flex items-start gap-2 border rounded-md p-3 text-sm cursor-pointer"
                >
                  <input
                    type="radio"
                    name="address"
                    checked={selectedAddressId === a.id}
                    onChange={() => setSelectedAddressId(a.id)}
                    className="mt-0.5"
                  />
                  <span>
                    <span className="font-medium">{a.label}</span> — {a.line1}, {a.city}
                  </span>
                </label>
              ))}

              {!showAddForm && (
                <button
                  type="button"
                  onClick={() => setShowAddForm(true)}
                  className="text-sm text-blue-600 underline"
                >
                  + Add a new address
                </button>
              )}

              {showAddForm && (
                <AddressForm
                  onSaved={() => {
                    setShowAddForm(false);
                    loadAddresses();
                  }}
                  onCancel={addresses.length > 0 ? () => setShowAddForm(false) : undefined}
                />
              )}
            </div>
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}

          <button
            type="submit"
            disabled={loading || (needsAddress && !selectedAddressId) || cartItems.length === 0}
            className="w-full bg-blue-600 text-white rounded-md py-2 text-sm font-medium disabled:opacity-50"
          >
            {loading ? "Creating order…" : "Continue to payment"}
          </button>

          <p className="text-xs text-gray-400 text-center">
            Test mode — card 4111 1111 1111 1111, any future expiry, any CVC/OTP.
          </p>
        </form>
      )}
    </main>
  );
}

// Opens Razorpay's own hosted payment popup. Razorpay's client-side
// `handler` result isn't trustworthy on its own (it's just what the
// browser says happened) — but it does hand back a signed proof
// (razorpay_payment_id/order_id/signature) that only Razorpay itself
// could have produced, so we send that straight to POST
// /orders/verify-payment, which re-derives and checks that signature
// server-side before confirming anything. That's what actually flips
// the order to "confirmed" here — not this callback by itself. The
// signed Razorpay webhook (routers/webhooks.py) still runs too and can
// confirm the same order independently; either one landing first is
// fine (see core/payment_confirmation.py's docstring on the backend for
// why both exist).
async function openRazorpayCheckout(
  data: CheckoutResponse,
  setError: (msg: string | null) => void
) {
  try {
    await loadRazorpayScript();
  } catch {
    setError("Couldn't load the payment window. Please check your connection and retry.");
    return;
  }

  const amountInPaise = Math.round(parseFloat(data.total_amount) * 100);

  const razorpay = new (window as any).Razorpay({
    key: data.razorpay_key_id,
    order_id: data.razorpay_order_id,
    amount: amountInPaise,
    currency: "INR",
    name: "LocalMart",
    description: `Order${data.orders.length > 1 ? "s" : ""} #${data.orders
      .map((o) => o.id.slice(0, 8))
      .join(", ")}`,
    handler: async function (response: {
      razorpay_order_id: string;
      razorpay_payment_id: string;
      razorpay_signature: string;
    }) {
      try {
        await apiFetch("/orders/verify-payment", {
          method: "POST",
          body: JSON.stringify({
            razorpay_order_id: response.razorpay_order_id,
            razorpay_payment_id: response.razorpay_payment_id,
            razorpay_signature: response.razorpay_signature,
          }),
        });
        setError(null);
      } catch {
        // Verification itself failed to go through (e.g. a network
        // blip right after payment) — not a sign the payment failed.
        // The webhook is still in flight independently and the order
        // tracking page keeps polling, so this stays reassuring rather
        // than alarming.
        setError("Payment received — confirming your order now. This can take a moment.");
      }
    },
    modal: {
      ondismiss: function () {
        setError("Payment window closed before completing payment. You can retry below.");
      },
    },
  });

  razorpay.on("payment.failed", function () {
    setError("Payment failed. You can retry below.");
  });

  razorpay.open();
}
