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

type CheckoutResponse = {
  orders: { id: string; shop_id: string; total_amount: string }[];
  razorpay_order_id: string;
  razorpay_key_id: string;
  total_amount: string;
};

export default function CheckoutPage() {
  // One idempotency key for this checkout attempt, generated once when
  // the page loads and reused across retries of that SAME attempt — this
  // is what lets the backend safely dedupe a retried request instead of
  // creating a second set of orders and charging twice.
  const idempotencyKey = useMemo(generateIdempotencyKey, []);

  const [addresses, setAddresses] = useState<Address[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [loadingAddresses, setLoadingAddresses] = useState(true);

  const [checkoutResult, setCheckoutResult] = useState<CheckoutResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

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

  async function startCheckout(e: FormEvent) {
    e.preventDefault();
    if (!selectedAddressId) {
      setError("Please add or select a delivery address.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data: CheckoutResponse = await apiFetch("/orders", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ address_id: selectedAddressId }),
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
  // shopper straight to order tracking — actual confirmation happens
  // asynchronously via the Razorpay webhook, and that page already polls
  // for it (see app/orders/[id]/page.tsx).
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

      {loadingAddresses ? (
        <p className="text-sm text-gray-400">Loading addresses…</p>
      ) : (
        <form onSubmit={startCheckout} className="space-y-4">
          <div className="space-y-2">
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
          </div>

          {showAddForm && (
            <AddressForm
              onSaved={() => {
                setShowAddForm(false);
                loadAddresses();
              }}
              onCancel={addresses.length > 0 ? () => setShowAddForm(false) : undefined}
            />
          )}

          {error && <p className="text-sm text-red-500">{error}</p>}

          <button
            type="submit"
            disabled={loading || !selectedAddressId}
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

// Opens Razorpay's own hosted payment popup. We don't confirm payment
// success from the popup's callback here — Razorpay's client-side
// `handler` result isn't itself trustworthy (it's just what the browser
// says happened), so the actual order confirmation only ever comes from
// the signed server-to-server webhook in routers/webhooks.py. This just
// gives the shopper immediate visual feedback and lets them retry if they
// close the popup or the payment fails.
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
    handler: function () {
      // Payment succeeded from the browser's point of view. The order
      // tracking page (already linked below) polls the backend and will
      // flip to "Confirmed" once the webhook has actually landed.
      setError(null);
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
