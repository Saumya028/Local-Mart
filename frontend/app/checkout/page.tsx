"use client";

import { FormEvent, useMemo, useState } from "react";
import { loadStripe, Stripe } from "@stripe/stripe-js";
import {
  CardElement,
  Elements,
  useElements,
  useStripe,
} from "@stripe/react-stripe-js";
import { apiFetch } from "@/lib/apiClient";

const stripePromise: Promise<Stripe | null> = loadStripe(
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY || ""
);

// crypto.randomUUID() isn't guaranteed to exist in every server runtime
// this component might briefly render under during SSR, so we fall back
// rather than risk a build-time crash on an older Node version.
function generateIdempotencyKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

type CheckoutResponse = {
  orders: { id: string; shop_id: string; total_amount: string }[];
  client_secret: string | null;
  total_amount: string;
};

export default function CheckoutPage() {
  // One idempotency key for this checkout attempt, generated once when
  // the page loads and reused across retries of that SAME attempt (e.g.
  // the network hiccups and the button gets clicked again) — this is
  // what lets the backend safely dedupe a retried request instead of
  // creating a second set of orders and charging twice.
  const idempotencyKey = useMemo(generateIdempotencyKey, []);

  const [address, setAddress] = useState("");
  const [checkoutResult, setCheckoutResult] = useState<CheckoutResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function startCheckout(e: FormEvent) {
    e.preventDefault();
    if (!address.trim()) {
      setError("Please enter a delivery address.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const data: CheckoutResponse = await apiFetch("/orders", {
        method: "POST",
        headers: { "Idempotency-Key": idempotencyKey },
        body: JSON.stringify({ delivery_address: address }),
      });
      setCheckoutResult(data);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  // Once the backend has created the (pending) orders and handed back a
  // Stripe client_secret, switch to the payment step — wrapped in
  // <Elements> so CardElement/useStripe/useElements below have access to
  // the Stripe.js instance.
  if (checkoutResult?.client_secret) {
    return (
      <main className="max-w-md mx-auto px-6 py-10">
        <Elements stripe={stripePromise}>
          <PaymentStep
            clientSecret={checkoutResult.client_secret}
            orderIds={checkoutResult.orders.map((o) => o.id)}
            total={checkoutResult.total_amount}
          />
        </Elements>
      </main>
    );
  }

  return (
    <main className="max-w-md mx-auto px-6 py-10 space-y-4">
      <h1 className="text-2xl font-bold">Checkout</h1>

      <form onSubmit={startCheckout} className="space-y-4">
        <textarea
          placeholder="Delivery address"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          rows={3}
          className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        {error && <p className="text-sm text-red-500">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white rounded-md py-2 text-sm font-medium disabled:opacity-50"
        >
          {loading ? "Creating order…" : "Continue to payment"}
        </button>
      </form>
    </main>
  );
}

function PaymentStep({
  clientSecret,
  orderIds,
  total,
}: {
  clientSecret: string;
  orderIds: string[];
  total: string;
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [status, setStatus] = useState<"idle" | "paying" | "succeeded" | "failed">("idle");
  const [error, setError] = useState<string | null>(null);

  async function handlePay(e: FormEvent) {
    e.preventDefault();
    if (!stripe || !elements) return;

    const cardElement = elements.getElement(CardElement);
    if (!cardElement) return;

    setStatus("paying");
    setError(null);

    // confirmCardPayment takes the clientSecret directly — this is the
    // legacy Card Element flow (as opposed to the newer Payment Element,
    // which manages the secret through <Elements options={{clientSecret}}>
    // instead). Either works; this one is simpler for a single card field.
    const result = await stripe.confirmCardPayment(clientSecret, {
      payment_method: { card: cardElement },
    });

    if (result.error) {
      setError(result.error.message ?? "Payment failed. Please try again.");
      setStatus("failed");
      return;
    }

    if (result.paymentIntent?.status === "succeeded") {
      setStatus("succeeded");
    }
  }

  if (status === "succeeded") {
    return (
      <div className="text-center space-y-2">
        <p className="text-lg font-semibold text-green-600">Payment successful!</p>
        <p className="text-sm text-gray-500">
          Order{orderIds.length > 1 ? "s" : ""} confirmed: {orderIds.join(", ")}
        </p>
        <p className="text-xs text-gray-400">
          (Order tracking / history page lands in Phase 4.)
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handlePay} className="space-y-4">
      <h2 className="text-xl font-bold">Pay ₹{total}</h2>

      <div className="border rounded-md p-3">
        <CardElement options={{ style: { base: { fontSize: "14px" } } }} />
      </div>

      <p className="text-xs text-gray-400">
        Test mode — card 4242 4242 4242 4242, any future expiry, any CVC.
      </p>

      {error && <p className="text-sm text-red-500">{error}</p>}

      <button
        type="submit"
        disabled={!stripe || status === "paying"}
        className="w-full bg-blue-600 text-white rounded-md py-2 text-sm font-medium disabled:opacity-50"
      >
        {status === "paying" ? "Processing…" : "Pay now"}
      </button>
    </form>
  );
}
