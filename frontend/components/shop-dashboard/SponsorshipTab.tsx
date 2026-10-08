"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";

type Plan = { key: string; name: string; days: number; price: string; is_active: boolean };
type PlansResponse = { mode: "razorpay" | "test" | null; razorpay_key_id: string | null; plans: Plan[] };
type Purchase = {
  id: string;
  plan_name: string;
  days: number;
  amount: string;
  paid_at: string | null;
  starts_at: string | null;
  ends_at: string | null;
};
type Status = { is_sponsored: boolean; sponsored_until: string | null; purchases: Purchase[] };
type Checkout = {
  purchase_id: string;
  mode: "razorpay" | "test";
  razorpay_key_id: string | null;
  razorpay_order_id: string | null;
  amount_paise: number | null;
  plan_name: string;
};

// Razorpay's hosted checkout popup. Loaded on demand so it never touches
// pages that don't sell anything.
declare global {
  interface Window {
    Razorpay?: new (options: Record<string, unknown>) => { open: () => void; on: (e: string, cb: () => void) => void };
  }
}
function loadRazorpay(): Promise<boolean> {
  return new Promise((resolve) => {
    if (window.Razorpay) return resolve(true);
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve(true);
    s.onerror = () => resolve(false);
    document.body.appendChild(s);
  });
}

const fmtDate = (iso: string | null) =>
  iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—";
const inr = (v: string | number) => `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

// Where a shop owner BUYS priority placement. Payment goes to LocalMart
// (not another shop); the moment it's verified the shop starts ranking
// above non-sponsored shops — no admin step in between.
export function SponsorshipTab({ shopId, approved }: { shopId: string; approved: boolean }) {
  const [plans, setPlans] = useState<PlansResponse | null>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [buying, setBuying] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, s] = await Promise.all([apiFetch("/sponsorship/plans"), apiFetch(`/sponsorship/shops/${shopId}`)]);
      setPlans(p);
      setStatus(s);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    }
  }, [shopId]);

  useEffect(() => {
    load();
  }, [load]);

  async function confirm(body: Record<string, unknown>) {
    const s: Status = await apiFetch(`/sponsorship/shops/${shopId}/confirm`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    setStatus(s);
    setNotice(`You're sponsored until ${fmtDate(s.sponsored_until)}. Your shop now ranks above non-sponsored shops.`);
  }

  async function buy(plan: Plan) {
    setBuying(plan.key);
    setError(null);
    setNotice(null);
    try {
      const co: Checkout = await apiFetch(`/sponsorship/shops/${shopId}/checkout`, {
        method: "POST",
        body: JSON.stringify({ plan_key: plan.key }),
      });

      if (co.mode === "test") {
        // Local development only — the server refuses this in production.
        await confirm({ purchase_id: co.purchase_id });
        setBuying(null);
        return;
      }

      if (!(await loadRazorpay()) || !window.Razorpay) {
        throw new Error("Couldn't load the payment window. Check your connection and try again.");
      }
      const rzp = new window.Razorpay({
        key: co.razorpay_key_id,
        order_id: co.razorpay_order_id,
        amount: co.amount_paise,
        currency: "INR",
        name: "LocalMart",
        description: `Shop promotion — ${co.plan_name}`,
        handler: async (resp: { razorpay_payment_id: string; razorpay_signature: string }) => {
          try {
            await confirm({
              purchase_id: co.purchase_id,
              razorpay_payment_id: resp.razorpay_payment_id,
              razorpay_signature: resp.razorpay_signature,
            });
          } catch (err) {
            setError(
              `Payment received but activation hasn't completed yet (${(err as Error).message}). It will activate automatically within a minute — refresh this page.`
            );
          } finally {
            setBuying(null);
          }
        },
        modal: { ondismiss: () => setBuying(null) },
      });
      rzp.open();
    } catch (err) {
      setError((err as Error).message);
      setBuying(null);
    }
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-3xl space-y-5">
      <div className="bg-white rounded-2xl border border-gray-100 p-5 sm:p-6">
        <h3 className="font-semibold text-gray-900">Get shown first</h3>
        <p className="text-sm text-gray-500 mt-1">
          Sponsored shops appear above other shops when nearby customers search for what you sell, and carry a
          &quot;Sponsored&quot; label. Customers still choose where to buy.
        </p>
        {status && (
          <p className={`mt-3 text-sm font-medium ${status.is_sponsored ? "text-emerald-600" : "text-gray-500"}`}>
            {status.is_sponsored
              ? `Active — sponsored until ${fmtDate(status.sponsored_until)}`
              : status.sponsored_until
              ? `Expired on ${fmtDate(status.sponsored_until)}`
              : "Not sponsored yet"}
          </p>
        )}
      </div>

      {error && <p className="text-sm text-red-500 break-words">{error}</p>}
      {notice && <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">{notice}</p>}

      {!approved ? (
        <p className="text-sm text-gray-500">You can buy a promotion once your shop has been approved.</p>
      ) : !plans ? (
        <p className="text-sm text-gray-400">Loading plans…</p>
      ) : plans.mode === null ? (
        <p className="text-sm text-gray-500">Promotions aren&apos;t available right now. Please check back soon.</p>
      ) : (
        <>
          {plans.mode === "test" && (
            <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
              Test mode — no real payment is taken. (Add Razorpay keys on the server to charge real money.)
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {plans.plans.map((p) => (
              <div key={p.key} className="bg-white rounded-2xl border border-gray-100 p-5 flex flex-col">
                <p className="text-sm font-medium text-gray-900">{p.name}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{inr(p.price)}</p>
                <p className="text-xs text-gray-400 mt-0.5">
                  {inr(Number(p.price) / p.days)}/day · {p.days} days
                </p>
                <button
                  onClick={() => buy(p)}
                  disabled={buying !== null}
                  className="mt-4 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg px-4 py-2 disabled:opacity-50"
                >
                  {buying === p.key ? "Processing…" : status?.is_sponsored ? "Extend" : "Buy"}
                </button>
              </div>
            ))}
          </div>
          {status?.is_sponsored && (
            <p className="text-xs text-gray-400">Extending adds days on top of your current end date — nothing is lost.</p>
          )}
        </>
      )}

      {status && status.purchases.length > 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 overflow-x-auto">
          <table className="w-full min-w-[420px] text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                <th className="px-5 py-3 font-medium">Plan</th>
                <th className="px-5 py-3 font-medium">Paid</th>
                <th className="px-5 py-3 font-medium">Amount</th>
                <th className="px-5 py-3 font-medium">Runs until</th>
              </tr>
            </thead>
            <tbody>
              {status.purchases.map((p) => (
                <tr key={p.id} className="border-b border-gray-50 last:border-0">
                  <td className="px-5 py-3 text-gray-900">{p.plan_name}</td>
                  <td className="px-5 py-3 text-gray-500">{fmtDate(p.paid_at)}</td>
                  <td className="px-5 py-3 text-gray-500">{inr(p.amount)}</td>
                  <td className="px-5 py-3 text-gray-500">{fmtDate(p.ends_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
