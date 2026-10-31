"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { CaseDetail } from "@/components/support/CaseDetail";
import { EvidenceUploader } from "@/components/support/EvidenceUploader";
import { SupportCase, errorMessage, fmt, statusMeta } from "@/components/support/types";

const RESPONSES = [
  { code: "accept_fix", label: "Agree to fix it", hint: "Refund, resend or replace — then the customer confirms." },
  { code: "offer", label: "Make an offer", hint: "A partial refund, a discount, or another alternative." },
  { code: "disagree", label: "Disagree", hint: "Explain your side. Photos help." },
  { code: "need_info", label: "Ask for more information", hint: "You can do this once per report." },
] as const;

/** Shop dashboard > Disputes: problems customers reported on this shop's orders. */
export function SupportTab({ shopId, openCaseId }: { shopId: string; openCaseId?: string | null }) {
  const [scope, setScope] = useState<"active" | "closed">("active");
  const [cases, setCases] = useState<SupportCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(openCaseId ?? null);

  const load = useCallback(async () => {
    try {
      setCases(await apiFetch(`/dashboard/shops/${shopId}/support?scope=${scope}`));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [shopId, scope]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {(["active", "closed"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setScope(s)}
            className={`text-sm rounded-full px-4 py-1.5 border ${scope === s ? "bg-blue-600 border-blue-600 text-white" : "border-gray-200 text-gray-600"}`}
          >
            {s === "active" ? "Open" : "Closed"}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-gray-400">Loading…</p>}
      {error && <p className="text-sm text-red-500">{error}</p>}
      {!loading && !error && cases.length === 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center">
          <p className="text-sm text-gray-500">{scope === "active" ? "No open problems. Nice work." : "Nothing closed yet."}</p>
        </div>
      )}

      {cases.map((c) => (
        <ShopCase key={c.id} c={c} open={selected === c.id} onToggle={() => setSelected(selected === c.id ? null : c.id)} onChanged={load} />
      ))}
    </div>
  );
}

function ShopCase({ c, open, onToggle, onChanged }: { c: SupportCase; open: boolean; onToggle: () => void; onChanged: () => void }) {
  const { profile } = useAuth();
  const meta = statusMeta(c, "shop");
  const [type, setType] = useState<(typeof RESPONSES)[number]["code"]>("accept_fix");
  const [message, setMessage] = useState("");
  const [photos, setPhotos] = useState<string[]>([]);
  const [doneNote, setDoneNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function post(path: string, body: unknown) {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/dashboard/support/cases/${c.id}/${path}`, { method: "POST", body: JSON.stringify(body) });
      setMessage("");
      setPhotos([]);
      await onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const choices = RESPONSES.filter((r) => r.code !== "need_info" || c.can_request_info);

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 space-y-3">
      <button onClick={onToggle} className="w-full text-left flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-gray-900">{c.reason_label}</p>
          <p className="text-xs text-gray-400">
            {c.order_ref && <>Order {c.order_ref} · </>}
            {c.customer_name} · {fmt(c.created_at)}
            {c.status === "open" && c.shop_due_at && <> · reply by {fmt(c.shop_due_at)}</>}
          </p>
        </div>
        <span className={`text-xs font-medium rounded-full px-2.5 py-1 whitespace-nowrap ${meta.className}`}>{meta.label}</span>
      </button>

      {open && (
        <div className="space-y-4 pt-2 border-t border-gray-100">
          <CaseDetail c={c} audience="shop" />

          {c.can_reply && (
            <div className="space-y-3 rounded-xl border border-blue-200 p-4">
              <p className="text-sm font-medium text-gray-900">Your reply</p>
              <p className="text-xs text-gray-500">You get one reply. The customer can then accept it or escalate to LocalMart support.</p>
              <div className="grid sm:grid-cols-2 gap-2">
                {choices.map((r) => (
                  <label key={r.code} className={`rounded-lg border px-3 py-2 cursor-pointer ${type === r.code ? "border-blue-600 bg-blue-50" : "border-gray-200"}`}>
                    <input type="radio" name={`resp-${c.id}`} className="sr-only" checked={type === r.code} onChange={() => setType(r.code)} />
                    <span className="block text-sm font-medium text-gray-900">{r.label}</span>
                    <span className="block text-xs text-gray-500">{r.hint}</span>
                  </label>
                ))}
              </div>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={3}
                maxLength={2000}
                placeholder={type === "need_info" ? "What do you need to know?" : "Explain what you'll do, or your side of the story."}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
              />
              {type !== "need_info" && profile && <EvidenceUploader userId={profile.id} photos={photos} onChange={setPhotos} max={5} />}
              <button
                disabled={busy || !message.trim()}
                onClick={() => post("reply", { response_type: type, message, photos: type === "need_info" ? [] : photos })}
                className="text-sm font-medium bg-blue-600 text-white rounded-lg px-4 py-2 disabled:opacity-50"
              >
                {type === "need_info" ? "Ask the customer" : "Send reply"}
              </button>
            </div>
          )}

          {c.can_mark_action_done && (
            <div className="space-y-2 rounded-xl border border-emerald-200 p-4">
              <p className="text-sm font-medium text-gray-900">
                LocalMart support asked you to {c.order_action === "refund" ? "refund the customer" : "resend the order"}
                {c.order_action_deadline && <> by {fmt(c.order_action_deadline)}</>}.
              </p>
              <p className="text-xs text-gray-500">Payments go directly between you and the customer. Confirm here once it&apos;s done.</p>
              <input
                value={doneNote}
                onChange={(e) => setDoneNote(e.target.value)}
                maxLength={1000}
                placeholder="Optional note, e.g. refunded by UPI"
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
              />
              <button disabled={busy} onClick={() => post("action-done", { note: doneNote })} className="text-sm font-medium bg-emerald-600 text-white rounded-lg px-4 py-2 disabled:opacity-50">
                I&apos;ve done this
              </button>
            </div>
          )}
          {error && <p className="text-sm text-red-500">{error}</p>}
        </div>
      )}
    </div>
  );
}
