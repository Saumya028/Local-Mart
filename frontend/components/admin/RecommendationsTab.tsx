"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";

type Run = {
  id: string;
  status: string;
  is_active: boolean;
  started_at: string;
  finished_at: string | null;
  duration_seconds: number | null;
  error: string | null;
  stats: Record<string, unknown>;
};
type Status = {
  enabled: boolean;
  holdout_pct: number;
  min_co_buyers: number;
  excluded_categories: string[];
  health: "ok" | "stale" | "no_model" | "disabled";
  active_run: Run | null;
  age_hours: number | null;
  stale_after_hours: number;
  recent_runs: Run[];
};
type Row = {
  surface: string;
  variant: string;
  impressions: number;
  clicks: number;
  add_to_carts: number;
  ctr: number;
  add_to_cart_rate: number;
  orders: number;
  revenue: string;
  revenue_per_1000_impressions: number;
};

const HEALTH: Record<Status["health"], { label: string; cls: string }> = {
  ok: { label: "Healthy", cls: "bg-emerald-50 text-emerald-700" },
  stale: { label: "Stale — nightly build is failing", cls: "bg-red-50 text-red-600" },
  no_model: { label: "No model built yet", cls: "bg-amber-50 text-amber-700" },
  disabled: { label: "Switched off (RECO_ENABLED=false)", cls: "bg-gray-100 text-gray-600" },
};
const RUN_CLS: Record<string, string> = {
  ready: "bg-emerald-50 text-emerald-700",
  rejected: "bg-amber-50 text-amber-700",
  failed: "bg-red-50 text-red-600",
  building: "bg-blue-50 text-blue-600",
};
const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
const when = (s: string | null) => (s ? new Date(s).toLocaleString("en-IN") : "—");

export function RecommendationsTab() {
  const [status, setStatus] = useState<Status | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [days, setDays] = useState(30);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch("/admin/recommendations/status").then(setStatus).catch((e) => setError((e as Error).message));
  }, []);
  useEffect(() => {
    apiFetch(`/admin/recommendations/metrics?days=${days}`)
      .then((r) => setRows(r.rows))
      .catch((e) => setError((e as Error).message));
  }, [days]);

  if (error) return <div className="p-4 sm:p-6 lg:p-8"><p className="text-sm text-red-500">{error}</p></div>;
  if (!status) return <div className="p-4 sm:p-6 lg:p-8"><p className="text-sm text-gray-400">Loading…</p></div>;

  const h = HEALTH[status.health];
  const stats = status.active_run?.stats ?? {};
  const num = (k: string) => (typeof stats[k] === "number" ? (stats[k] as number) : null);

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-5">
      <div className="bg-white rounded-2xl border border-gray-100 p-5 space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-semibold text-gray-900">Model status</h2>
          <span className={`text-xs font-medium rounded-full px-2.5 py-1 ${h.cls}`}>{h.label}</span>
        </div>
        <p className="text-sm text-gray-500">
          {status.active_run
            ? `Active model built ${status.age_hours}h ago (stale after ${status.stale_after_hours}h).`
            : "Run the nightly build job to create the first model."}
          {" "}Holdout {status.holdout_pct}% · min co-buyers {status.min_co_buyers} · excluded: {status.excluded_categories.join(", ") || "none"}
        </p>
        {status.active_run && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            {[
              ["Hit-rate@10", num("hit_rate") != null ? pct(num("hit_rate")!) : "—"],
              ["Popularity baseline", num("baseline_hit_rate") != null ? pct(num("baseline_hit_rate")!) : "—"],
              ["Customers evaluated", num("n_eval_users")?.toLocaleString("en-IN") ?? "—"],
              ["Catalog coverage", num("catalog_coverage") != null ? pct(num("catalog_coverage")!) : "—"],
            ].map(([k, v]) => (
              <div key={k} className="rounded-xl bg-gray-50 p-3">
                <p className="text-xs text-gray-400">{k}</p>
                <p className="font-semibold text-gray-900">{v}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-gray-900">Shelf performance</h2>
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="text-sm border rounded-lg px-2 py-1">
            {[7, 30, 90].map((d) => <option key={d} value={d}>Last {d} days</option>)}
          </select>
        </div>
        {rows.length === 0 ? (
          <p className="text-sm text-gray-400">No shelf activity recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400">
                  {["Shelf", "Arm", "Views", "Clicks", "CTR", "Add-to-cart", "Orders", "Revenue", "₹ / 1000 views"].map((c) => (
                    <th key={c} className="py-2 pr-4 font-medium whitespace-nowrap">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.surface + r.variant} className="border-t border-gray-50">
                    <td className="py-2 pr-4">{r.surface}</td>
                    <td className="py-2 pr-4">{r.variant}</td>
                    <td className="py-2 pr-4">{r.impressions.toLocaleString("en-IN")}</td>
                    <td className="py-2 pr-4">{r.clicks.toLocaleString("en-IN")}</td>
                    <td className="py-2 pr-4">{pct(r.ctr)}</td>
                    <td className="py-2 pr-4">{pct(r.add_to_cart_rate)}</td>
                    <td className="py-2 pr-4">{r.orders}</td>
                    <td className="py-2 pr-4">₹{Number(r.revenue).toLocaleString("en-IN")}</td>
                    <td className="py-2 pr-4">₹{r.revenue_per_1000_impressions.toLocaleString("en-IN")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-xs text-gray-400 mt-3">
          Orders/revenue count purchases of a product within 7 days of a click or add-to-cart on it. To measure lift,
          set RECO_HOLDOUT_PCT (e.g. 10) and compare the &quot;model&quot; and &quot;holdout&quot; rows.
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 p-5">
        <h2 className="font-semibold text-gray-900 mb-3">Recent builds</h2>
        <div className="space-y-2">
          {status.recent_runs.map((r) => (
            <div key={r.id} className="flex flex-wrap items-center gap-3 text-sm border-t border-gray-50 pt-2 first:border-0 first:pt-0">
              <span className={`text-xs font-medium rounded-full px-2.5 py-1 ${RUN_CLS[r.status] ?? "bg-gray-100 text-gray-600"}`}>{r.status}</span>
              {r.is_active && <span className="text-xs text-emerald-600 font-medium">live</span>}
              <span className="text-gray-500">{when(r.started_at)}</span>
              {r.duration_seconds != null && <span className="text-xs text-gray-400">{Math.round(r.duration_seconds)}s</span>}
              {r.error && <span className="text-xs text-red-500 truncate max-w-md">{r.error}</span>}
              {Array.isArray(r.stats?.gate_reasons) && (r.stats.gate_reasons as string[]).length > 0 && (
                <span className="text-xs text-amber-600">{(r.stats.gate_reasons as string[]).join(", ")}</span>
              )}
            </div>
          ))}
          {status.recent_runs.length === 0 && <p className="text-sm text-gray-400">No builds yet.</p>}
        </div>
      </div>
    </div>
  );
}
