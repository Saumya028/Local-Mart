"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { CaseDetail } from "@/components/support/CaseDetail";
import { EvidenceUploader } from "@/components/support/EvidenceUploader";
import { ReportModal } from "@/components/support/ReportModal";
import { SupportCase, errorMessage, fmtDate, statusMeta } from "@/components/support/types";

/** My Account > Support: every report I've filed, with what I can do next. */
export function SupportTab({ openCaseId, startNew }: { openCaseId?: string | null; startNew?: boolean }) {
  const { profile } = useAuth();
  const [cases, setCases] = useState<SupportCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(openCaseId ?? null);
  const [showNew, setShowNew] = useState(!!startNew);

  const load = useCallback(async () => {
    try {
      setCases(await apiFetch("/support/cases"));
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <p className="text-sm text-gray-400">Loading…</p>;

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl border border-gray-100 p-5 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-gray-600 max-w-md">
          Problem with an order? Open it from <b>My Orders</b> and choose <b>Report a problem</b>. For anything else, contact us here.
        </p>
        <button onClick={() => setShowNew(true)} className="text-sm font-medium bg-blue-600 text-white rounded-lg px-4 py-2">
          Contact LocalMart support
        </button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {cases.length === 0 && !error && (
        <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center">
          <p className="text-sm text-gray-500">You haven&apos;t reported anything.</p>
        </div>
      )}

      {cases.map((c) => (
        <CaseCard key={c.id} c={c} open={selected === c.id} onToggle={() => setSelected(selected === c.id ? null : c.id)} onChanged={load} userId={profile?.id} />
      ))}

      {showNew && (
        <ReportModal
          mode="general"
          onClose={() => setShowNew(false)}
          onSubmitted={(created) => {
            setShowNew(false);
            setSelected(created.id);
            load();
          }}
        />
      )}
    </div>
  );
}

function CaseCard({ c, open, onToggle, onChanged, userId }: { c: SupportCase; open: boolean; onToggle: () => void; onChanged: () => void; userId?: string }) {
  const meta = statusMeta(c, "customer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoText, setInfoText] = useState("");
  const [infoPhotos, setInfoPhotos] = useState<string[]>([]);
  const [escalating, setEscalating] = useState(false);
  const [note, setNote] = useState("");

  async function act(path: string, body?: unknown) {
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/support/cases/${c.id}/${path}`, { method: "POST", body: JSON.stringify(body ?? {}) });
      setEscalating(false);
      await onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 space-y-3">
      <button onClick={onToggle} className="w-full text-left flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-gray-900">{c.reason_label}</p>
          <p className="text-xs text-gray-400">
            {c.kind_label}
            {c.order_ref && <> · Order {c.order_ref}</>}
            {c.shop_name && <> · {c.shop_name}</>} · {fmtDate(c.created_at)}
          </p>
        </div>
        <span className={`text-xs font-medium rounded-full px-2.5 py-1 whitespace-nowrap ${meta.className}`}>{meta.label}</span>
      </button>

      {open && (
        <div className="space-y-4 pt-2 border-t border-gray-100">
          <CaseDetail c={c} audience="customer" />

          {c.can_reply_info && userId && (
            <div className="space-y-2 rounded-xl border border-amber-200 p-4">
              <p className="text-sm font-medium text-gray-900">Answer the shop</p>
              <textarea value={infoText} onChange={(e) => setInfoText(e.target.value)} rows={3} maxLength={1000} className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" />
              <EvidenceUploader userId={userId} photos={infoPhotos} onChange={setInfoPhotos} max={5} />
              <button
                disabled={busy || !infoText.trim()}
                onClick={() => act("info", { message: infoText, photos: infoPhotos })}
                className="text-sm font-medium bg-blue-600 text-white rounded-lg px-4 py-2 disabled:opacity-50"
              >
                Send to the shop
              </button>
            </div>
          )}

          {(c.can_accept || c.can_escalate) && (
            <div className="space-y-2">
              {c.auto_close_at && (c.status === "shop_replied" || c.status === "needs_info") && (
                <p className="text-xs text-gray-500">If you don&apos;t respond, this closes automatically on {fmtDate(c.auto_close_at)}.</p>
              )}
              {escalating && (
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                  maxLength={1000}
                  placeholder="Anything LocalMart support should know? (optional)"
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
                />
              )}
              <div className="flex flex-wrap gap-2">
                {c.can_accept && (
                  <button disabled={busy} onClick={() => act("accept")} className="text-sm font-medium border border-gray-200 rounded-lg px-4 py-2 text-gray-700 disabled:opacity-50">
                    {c.shop_response_type ? "I’m happy with this — close" : "Close this report"}
                  </button>
                )}
                {c.can_escalate &&
                  (escalating ? (
                    <button disabled={busy} onClick={() => act("escalate", { note })} className="text-sm font-medium bg-blue-600 text-white rounded-lg px-4 py-2 disabled:opacity-50">
                      Send to LocalMart support
                    </button>
                  ) : (
                    <button onClick={() => setEscalating(true)} className="text-sm font-medium text-blue-700 border border-blue-200 rounded-lg px-4 py-2">
                      Escalate to LocalMart support
                    </button>
                  ))}
              </div>
            </div>
          )}
          {error && <p className="text-sm text-red-500">{error}</p>}
        </div>
      )}
    </div>
  );
}
