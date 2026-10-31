"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { CaseDetail } from "@/components/support/CaseDetail";
import { SupportCase, errorMessage, fmt, statusMeta } from "@/components/support/types";

type Summary = { escalated: number; overdue: number; direct_reports: number; action_overdue: number; open_total: number };

const VIEWS = [
  { key: "attention", label: "Needs attention" },
  { key: "escalated", label: "Escalated" },
  { key: "overdue", label: "Shop overdue" },
  { key: "reports", label: "Shop reports" },
  { key: "general", label: "General" },
  { key: "action", label: "Ordered actions" },
  { key: "active", label: "All open" },
  { key: "closed", label: "Closed" },
] as const;
type ViewKey = (typeof VIEWS)[number]["key"];

export function SupportTab({ search, openCaseId, onAttentionCount }: { search: string; openCaseId?: string | null; onAttentionCount?: (n: number) => void }) {
  const [view, setView] = useState<ViewKey>("attention");
  const [cases, setCases] = useState<SupportCase[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(openCaseId ?? null);

  const load = useCallback(async () => {
    try {
      const qs = new URLSearchParams({ view });
      if (search.trim()) qs.set("q", search.trim());
      const [list, sum]: [SupportCase[], Summary] = await Promise.all([apiFetch(`/admin/support/cases?${qs}`), apiFetch("/admin/support/summary")]);
      setCases(list);
      setSummary(sum);
      onAttentionCount?.(sum.escalated + sum.overdue + sum.direct_reports + sum.action_overdue);
      setError(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [view, search, onAttentionCount]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  const count = (k: ViewKey) =>
    !summary ? null : k === "escalated" ? summary.escalated : k === "overdue" ? summary.overdue : k === "reports" ? summary.direct_reports : k === "action" ? summary.action_overdue : k === "active" ? summary.open_total : null;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {VIEWS.map((v) => (
          <button
            key={v.key}
            onClick={() => setView(v.key)}
            className={`text-sm rounded-full px-3.5 py-1.5 border ${view === v.key ? "bg-blue-600 border-blue-600 text-white" : "border-gray-200 text-gray-600 bg-white"}`}
          >
            {v.label}
            {count(v.key) ? <span className={`ml-1.5 text-xs ${view === v.key ? "text-blue-100" : "text-gray-400"}`}>{count(v.key)}</span> : null}
          </button>
        ))}
      </div>

      {loading && <p className="text-sm text-gray-400">Loading…</p>}
      {error && <p className="text-sm text-red-500">{error}</p>}
      {!loading && !error && cases.length === 0 && (
        <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center">
          <p className="text-sm text-gray-500">Nothing here.</p>
        </div>
      )}

      {cases.map((c) => (
        <AdminCase key={c.id} c={c} open={selected === c.id} onToggle={() => setSelected(selected === c.id ? null : c.id)} onChanged={load} />
      ))}
    </div>
  );
}

function AdminCase({ c, open, onToggle, onChanged }: { c: SupportCase; open: boolean; onToggle: () => void; onChanged: () => void }) {
  const meta = statusMeta(c, "admin");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ruling form
  const [ruling, setRuling] = useState<"customer" | "shop" | "no_fault">("customer");
  const [note, setNote] = useState("");
  const [orderAction, setOrderAction] = useState<"" | "refund" | "resend">("");
  const [days, setDays] = useState(3);
  const [actionNote, setActionNote] = useState("");
  const [internal, setInternal] = useState(c.internal_note ?? "");
  // review form
  const [outcome, setOutcome] = useState<"action_taken" | "no_action">("no_action");
  // shop action form
  const [shopAction, setShopAction] = useState<"warn" | "hide_shop" | "suspend_owner">("warn");
  const [shopNote, setShopNote] = useState("");
  const [flagNote, setFlagNote] = useState("");

  async function run(path: string, body: unknown, confirmText?: string) {
    if (confirmText && !window.confirm(confirmText)) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch(`/admin/support/${path}`, { method: "POST", body: JSON.stringify(body) });
      await onChanged();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const stats = c.customer_stats;
  const input = "w-full rounded-lg border border-gray-200 px-3 py-2 text-sm";
  const btn = "text-sm font-medium rounded-lg px-4 py-2 disabled:opacity-50";

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-5 space-y-3">
      <button onClick={onToggle} className="w-full text-left flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold text-gray-900">{c.reason_label}</p>
          <p className="text-xs text-gray-400">
            {c.kind_label}
            {c.order_ref && <> · Order {c.order_ref}</>}
            {c.shop_name && <> · {c.shop_name}</>} · {c.customer_name} · {fmt(c.created_at)}
          </p>
        </div>
        <span className={`text-xs font-medium rounded-full px-2.5 py-1 whitespace-nowrap ${meta.className}`}>{meta.label}</span>
      </button>

      {open && (
        <div className="space-y-4 pt-2 border-t border-gray-100">
          {stats && (
            <div className={`rounded-xl px-4 py-3 text-sm ${stats.suggest_flag ? "bg-amber-50 text-amber-800" : "bg-gray-50 text-gray-600"}`}>
              <p>
                This customer has filed {stats.cases_total} report{stats.cases_total === 1 ? "" : "s"}; {stats.ruled_against_60d} ruled against them in the last 60 days.
                {stats.flagged_at && <b> Flagged for false disputes{stats.flag_note ? `: ${stats.flag_note}` : ""}.</b>}
              </p>
              {stats.suggest_flag && <p className="text-xs mt-1">That&apos;s enough to consider flagging them. A flag doesn&apos;t restrict the account on its own.</p>}
              <div className="flex flex-wrap gap-2 mt-2">
                {!stats.flagged_at && (
                  <input value={flagNote} onChange={(e) => setFlagNote(e.target.value)} placeholder="Note (optional)" className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs bg-white" maxLength={300} />
                )}
                <button
                  disabled={busy || !c.customer_id}
                  onClick={() => run(`customers/${c.customer_id}/flag`, { flagged: !stats.flagged_at, note: flagNote || null })}
                  className="text-xs font-medium rounded-lg px-3 py-1.5 border border-amber-400 text-amber-800 bg-white disabled:opacity-50"
                >
                  {stats.flagged_at ? "Remove flag" : "Flag customer"}
                </button>
              </div>
            </div>
          )}

          <CaseDetail c={c} audience="admin" />

          {c.can_rule && (
            <div className="space-y-3 rounded-xl border border-blue-200 p-4">
              <p className="text-sm font-medium text-gray-900">Rule on this dispute</p>
              <div className="grid grid-cols-3 gap-2">
                {(
                  [
                    ["customer", "For the customer"],
                    ["shop", "For the shop"],
                    ["no_fault", "No fault"],
                  ] as const
                ).map(([k, label]) => (
                  <button key={k} onClick={() => { setRuling(k); if (k !== "customer") setOrderAction(""); }} className={`rounded-lg border px-2 py-2 text-sm ${ruling === k ? "border-blue-600 bg-blue-50 text-blue-700 font-medium" : "border-gray-200 text-gray-600"}`}>
                    {label}
                  </button>
                ))}
              </div>
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={1000} placeholder="Decision note — shown to BOTH the customer and the shop" className={input} />
              {ruling === "customer" && (
                <div className="grid sm:grid-cols-3 gap-2">
                  <select value={orderAction} onChange={(e) => setOrderAction(e.target.value as "" | "refund" | "resend")} className={`${input} bg-white sm:col-span-2`}>
                    <option value="">No instruction to the shop</option>
                    <option value="refund">Order the shop to refund</option>
                    <option value="resend">Order the shop to resend</option>
                  </select>
                  {orderAction && (
                    <label className="flex items-center gap-2 text-sm text-gray-600">
                      within
                      <input type="number" min={1} max={30} value={days} onChange={(e) => setDays(Number(e.target.value) || 1)} className="w-16 rounded-lg border border-gray-200 px-2 py-2 text-sm" />
                      days
                    </label>
                  )}
                  {orderAction && <input value={actionNote} onChange={(e) => setActionNote(e.target.value)} maxLength={1000} placeholder="Instruction details for the shop (optional)" className={`${input} sm:col-span-3`} />}
                </div>
              )}
              <textarea value={internal} onChange={(e) => setInternal(e.target.value)} rows={2} maxLength={1000} placeholder="Internal note — admins only" className={input} />
              <button
                disabled={busy || !note.trim()}
                onClick={() => run(`cases/${c.id}/rule`, { ruling, note, order_action: orderAction || null, action_days: days, action_note: actionNote || null, internal_note: internal || null })}
                className={`${btn} bg-blue-600 text-white`}
              >
                Record ruling
              </button>
            </div>
          )}

          {c.can_review && (
            <div className="space-y-3 rounded-xl border border-blue-200 p-4">
              <p className="text-sm font-medium text-gray-900">Review this {c.kind === "shop_report" ? "shop report" : "issue"}</p>
              <p className="text-xs text-gray-500">The person who reported it will only see “action taken” or “no action needed”.</p>
              <div className="grid grid-cols-2 gap-2">
                {(
                  [
                    ["action_taken", "Action taken"],
                    ["no_action", "No action needed"],
                  ] as const
                ).map(([k, label]) => (
                  <button key={k} onClick={() => setOutcome(k)} className={`rounded-lg border px-2 py-2 text-sm ${outcome === k ? "border-blue-600 bg-blue-50 text-blue-700 font-medium" : "border-gray-200 text-gray-600"}`}>
                    {label}
                  </button>
                ))}
              </div>
              <textarea value={internal} onChange={(e) => setInternal(e.target.value)} rows={2} maxLength={1000} placeholder="Internal note — admins only" className={input} />
              <button disabled={busy} onClick={() => run(`cases/${c.id}/review`, { outcome, internal_note: internal || null })} className={`${btn} bg-blue-600 text-white`}>
                Close as reviewed
              </button>
            </div>
          )}

          {c.can_mark_action_done && (
            <button disabled={busy} onClick={() => run(`cases/${c.id}/action-done`, {}, "Confirm that the refund/resend has happened?")} className={`${btn} border border-emerald-300 text-emerald-700`}>
              Mark ordered {c.order_action} as done
            </button>
          )}

          {c.shop_id && (
            <div className="space-y-2 rounded-xl border border-gray-200 p-4">
              <p className="text-sm font-medium text-gray-900">Act on {c.shop_name ?? "the shop"}</p>
              <select value={shopAction} onChange={(e) => setShopAction(e.target.value as typeof shopAction)} className={`${input} bg-white`}>
                <option value="warn">Warn the shop (they see your note)</option>
                <option value="hide_shop">Hide the shop from customers</option>
                <option value="suspend_owner">Suspend the owner’s account (shop stays visible unless hidden)</option>
              </select>
              <input value={shopNote} onChange={(e) => setShopNote(e.target.value)} maxLength={1000} placeholder={shopAction === "suspend_owner" ? "Note (optional)" : "Note for the shop"} className={input} />
              <button
                disabled={busy || (shopAction !== "suspend_owner" && !shopNote.trim())}
                onClick={() =>
                  run(
                    `cases/${c.id}/shop-action`,
                    { action: shopAction, note: shopNote || null },
                    shopAction === "warn" ? undefined : shopAction === "hide_shop" ? "Hide this shop from customers?" : "Suspend the owner’s account? They won’t be able to log in."
                  )
                }
                className={`${btn} border border-gray-300 text-gray-800`}
              >
                Apply
              </button>
            </div>
          )}

          {c.status === "resolved" && (
            <div className="space-y-2">
              <textarea value={internal} onChange={(e) => setInternal(e.target.value)} rows={2} maxLength={2000} placeholder="Internal note — admins only" className={input} />
              <button disabled={busy} onClick={() => run(`cases/${c.id}/note`, { internal_note: internal || null })} className={`${btn} border border-gray-300 text-gray-700`}>
                Save note
              </button>
            </div>
          )}
          {error && <p className="text-sm text-red-500">{error}</p>}
        </div>
      )}
    </div>
  );
}
