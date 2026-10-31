"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { EvidenceUploader } from "./EvidenceUploader";
import { CaseKind, SupportCase, SupportOptions, errorMessage } from "./types";

type Mode = "order" | "shop" | "general";

/**
 * The "Report a problem" flow, in three flavours:
 *   order    about one of the customer's orders (an order problem or a payment problem)
 *   shop     report a shop — goes straight to LocalMart support
 *   general  an app/account issue — goes straight to LocalMart support
 */
export function ReportModal({
  mode,
  orderId,
  orderRef,
  shopId,
  shopName,
  onClose,
  onSubmitted,
}: {
  mode: Mode;
  orderId?: string;
  orderRef?: string;
  shopId?: string;
  shopName?: string;
  onClose: () => void;
  onSubmitted: (c: SupportCase) => void;
}) {
  const { profile } = useAuth();
  const [options, setOptions] = useState<SupportOptions | null>(null);
  const [orderKind, setOrderKind] = useState<"order_problem" | "payment_problem">("order_problem");
  const kind: CaseKind = mode === "order" ? orderKind : mode === "shop" ? "shop_report" : "general";
  const [reason, setReason] = useState("");
  const [description, setDescription] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/support/options")
      .then(setOptions)
      .catch((err) => setError(errorMessage(err)));
  }, []);

  const reasons = options?.reasons[kind] ?? [];
  useEffect(() => {
    setReason(reasons[0]?.code ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind, options]);

  async function submit() {
    if (!description.trim()) {
      setError("Please tell us what happened.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const created: SupportCase = await apiFetch("/support/cases", {
        method: "POST",
        body: JSON.stringify({
          kind,
          reason,
          description,
          photos,
          order_id: mode === "order" ? orderId : null,
          shop_id: mode === "shop" ? shopId : null,
        }),
      });
      onSubmitted(created);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  const title =
    mode === "order" ? `Report a problem${orderRef ? ` with order ${orderRef}` : ""}` : mode === "shop" ? `Report ${shopName ?? "this shop"}` : "Contact LocalMart support";

  const how =
    mode === "order"
      ? `${shopName ?? "The shop"} will reply first${options ? ` (within ${options.shop_reply_hours} hours)` : ""}. If that doesn't sort it out, you can escalate to LocalMart support at any time.`
      : mode === "shop"
        ? "This goes straight to LocalMart support. The shop is told a report exists, but not who sent it or what you wrote."
        : "This goes straight to LocalMart support.";

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-end sm:items-center justify-center p-0 sm:p-4" role="dialog" aria-modal="true" aria-label={title}>
      <div className="bg-white w-full sm:max-w-lg rounded-t-2xl sm:rounded-2xl max-h-[92vh] overflow-y-auto p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <h2 className="text-lg font-bold text-gray-900">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="text-gray-400 hover:text-gray-700 text-xl leading-none">
            ×
          </button>
        </div>

        {mode === "order" && (
          <div className="grid grid-cols-2 gap-2">
            {(
              [
                ["order_problem", "Problem with my order"],
                ["payment_problem", "Payment problem"],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                type="button"
                onClick={() => setOrderKind(k)}
                className={`rounded-lg border px-3 py-2 text-sm ${orderKind === k ? "border-blue-600 bg-blue-50 text-blue-700 font-medium" : "border-gray-200 text-gray-600"}`}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        <label className="block space-y-1">
          <span className="text-sm font-medium text-gray-700">What went wrong?</span>
          <select value={reason} onChange={(e) => setReason(e.target.value)} className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm bg-white">
            {reasons.map((r) => (
              <option key={r.code} value={r.code}>
                {r.label}
              </option>
            ))}
          </select>
        </label>

        <label className="block space-y-1">
          <span className="text-sm font-medium text-gray-700">Tell us what happened</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            maxLength={2000}
            className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
            placeholder={mode === "order" ? "e.g. The jar arrived cracked and the lid was open." : "Add as much detail as you can."}
          />
        </label>

        {profile && options && (
          <div className="space-y-1">
            <span className="text-sm font-medium text-gray-700">Photos (optional)</span>
            <EvidenceUploader userId={profile.id} photos={photos} onChange={setPhotos} max={options.max_photos} />
          </div>
        )}

        <p className="text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2">{how}</p>
        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex justify-end gap-2 pt-1">
          <button onClick={onClose} className="px-4 py-2 text-sm rounded-lg border border-gray-200 text-gray-600">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={submitting || !options}
            className="px-4 py-2 text-sm rounded-lg bg-blue-600 text-white font-medium disabled:opacity-50"
          >
            {submitting ? "Sending…" : "Send report"}
          </button>
        </div>
      </div>
    </div>
  );
}
