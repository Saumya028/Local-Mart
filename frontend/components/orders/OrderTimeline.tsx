"use client";

export type OrderEvent = {
  id: string;
  kind: string;
  from_status: string | null;
  to_status: string | null;
  actor_role: string;
  actor: string;
  note: string | null;
  meta: Record<string, unknown> | null;
  created_at: string;
};

const STATUS_LABEL: Record<string, string> = {
  confirmed: "Order confirmed",
  preparing: "Shop started preparing",
  packing: "Packing",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  ready_for_pickup: "Ready for pickup",
  picked_up: "Picked up",
  cancelled: "Cancelled",
};

function methodName(m: unknown) {
  return m === "upi" ? "UPI" : m === "cash" ? "cash" : String(m ?? "");
}

function describe(e: OrderEvent): { label: string; tone: "ok" | "bad" | "neutral" } {
  const reqType = e.meta?.request_type === "exchange" ? "Exchange" : "Return";
  switch (e.kind) {
    case "order_placed":
      return { label: e.meta?.source === "exchange" ? "Replacement order created" : "Order placed", tone: "neutral" };
    case "status_changed":
      return {
        label: STATUS_LABEL[e.to_status ?? ""] ?? `Status: ${e.to_status}`,
        tone: e.to_status === "delivered" || e.to_status === "picked_up" ? "ok" : "neutral",
      };
    case "payment_submitted":
      return { label: "Payment reported by customer", tone: "neutral" };
    case "payment_confirmed":
      return { label: e.meta?.auto ? "Cash collected" : "Payment confirmed", tone: "ok" };
    case "payment_rejected":
      return { label: "Shop didn’t receive the payment", tone: "bad" };
    case "payment_method_changed":
      return { label: `Payment method changed to ${methodName(e.meta?.to_method)}`, tone: "neutral" };
    case "order_cancelled":
      return { label: "Order cancelled", tone: "bad" };
    case "return_requested":
      return { label: `${reqType} requested`, tone: "neutral" };
    case "return_approved":
      return { label: `${reqType} approved`, tone: "ok" };
    case "return_rejected":
      return { label: `${reqType} declined`, tone: "bad" };
    case "return_completed":
      return { label: `${reqType} completed`, tone: "ok" };
    case "return_cancelled":
      return { label: `${reqType} request withdrawn`, tone: "neutral" };
    case "difference_reported":
      return { label: "Exchange top-up reported", tone: "neutral" };
    case "difference_confirmed":
      return { label: "Exchange top-up confirmed", tone: "ok" };
    default:
      return { label: e.kind.replace(/_/g, " "), tone: "neutral" };
  }
}

const DOT = { ok: "bg-emerald-500", bad: "bg-red-500", neutral: "bg-blue-500" } as const;

/**
 * Vertical history of an order — who did what, when. `showActor` is on for
 * the shop/admin view (where `actor` carries a name) and for the customer
 * view too (where the backend only ever sends "You" / "The shop" / "Automatic").
 */
export function OrderTimeline({ events }: { events: OrderEvent[] }) {
  if (events.length === 0) {
    return <p className="text-sm text-gray-400">No history recorded for this order yet.</p>;
  }
  return (
    <ol className="relative border-l border-gray-200 ml-2 space-y-4">
      {events.map((e) => {
        const { label, tone } = describe(e);
        const proof = typeof e.meta?.delivery_proof_photo_url === "string" ? e.meta.delivery_proof_photo_url : null;
        const utr = typeof e.meta?.utr === "string" ? e.meta.utr : null;
        return (
          <li key={e.id} className="pl-5 relative">
            <span className={`absolute -left-[5px] top-1.5 w-2.5 h-2.5 rounded-full ${DOT[tone]}`} aria-hidden="true" />
            <p className="text-sm font-medium text-gray-900">{label}</p>
            <p className="text-xs text-gray-400">
              {new Date(e.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })} · {e.actor}
            </p>
            {utr && <p className="text-xs text-gray-500 mt-0.5">UTR: {utr}</p>}
            {e.note && <p className="text-xs text-gray-500 mt-0.5">{e.note}</p>}
            {proof && (
              <a href={proof} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline mt-0.5 inline-block">
                View delivery photo
              </a>
            )}
          </li>
        );
      })}
    </ol>
  );
}
