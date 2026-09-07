"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { LineChart } from "./Charts";
import { DashboardMetrics, formatINR, statusMeta, timeAgo } from "./types";

function pctChange(today: number, yesterday: number): number | null {
  if (yesterday === 0) return today === 0 ? 0 : null;
  return ((today - yesterday) / yesterday) * 100;
}

function ChangeBadge({ pct, invert = false }: { pct: number | null; invert?: boolean }) {
  if (pct === null) return null;
  const up = pct >= 0;
  const good = invert ? !up : up;
  return (
    <span className={`text-xs font-medium ${good ? "text-emerald-600" : "text-red-500"}`}>
      {up ? "↑" : "↓"} {Math.abs(pct).toFixed(0)}%
    </span>
  );
}

export function DashboardTab({ shopId, onGoToOrders }: { shopId: string; onGoToOrders: () => void }) {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    apiFetch(`/dashboard/metrics?shop_id=${shopId}`)
      .then(setMetrics)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [shopId]);

  if (loading) return <p className="text-sm text-gray-400 p-8">Loading dashboard…</p>;
  if (error) return <p className="text-sm text-red-500 p-8">{error}</p>;
  if (!metrics) return null;

  const orderChange = pctChange(metrics.today_orders, metrics.yesterday_orders);
  const revenueChange = pctChange(Number(metrics.today_revenue), Number(metrics.yesterday_revenue));

  return (
    <div className="p-8 space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <MetricCard
          label="Today's Revenue"
          value={formatINR(metrics.today_revenue)}
          sub={<ChangeBadge pct={revenueChange} />}
          subLabel="vs yesterday"
          icon={<CoinIcon />}
          iconBg="bg-blue-50 text-blue-600"
        />
        <MetricCard
          label="Today's Orders"
          value={String(metrics.today_orders)}
          sub={<ChangeBadge pct={orderChange} />}
          subLabel={orderChange === null ? "" : "vs yesterday"}
          icon={<BagIcon />}
          iconBg="bg-emerald-50 text-emerald-600"
        />
        <MetricCard
          label="Pending Orders"
          value={String(metrics.pending_orders)}
          sub={
            metrics.urgent_pending_orders > 0 ? (
              <span className="text-xs font-medium text-red-500">↓ {metrics.urgent_pending_orders} urgent</span>
            ) : (
              <span className="text-xs text-gray-400">all caught up</span>
            )
          }
          subLabel=""
          icon={<AlertIcon />}
          iconBg="bg-amber-50 text-amber-600"
          onClick={onGoToOrders}
        />
        <MetricCard
          label="Avg. Rating"
          value={metrics.avg_rating.toFixed(1)}
          sub={<span className="text-xs text-gray-400">shop rating</span>}
          subLabel=""
          icon={<StarIcon />}
          iconBg="bg-yellow-50 text-yellow-600"
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className="xl:col-span-2 bg-white border border-gray-100 rounded-2xl p-5">
          <div className="flex items-center justify-between mb-1">
            <div>
              <h2 className="font-semibold text-gray-900">Revenue This Week</h2>
              <p className="text-xs text-gray-400">
                {formatINR(metrics.week_revenue_total)} total
                {metrics.week_revenue_change_pct !== null && (
                  <>
                    {" "}
                    · <ChangeBadge pct={metrics.week_revenue_change_pct} /> vs last week
                  </>
                )}
              </p>
            </div>
          </div>
          <LineChart points={metrics.revenue_by_day} formatY={(n) => `₹${Math.round(n / 1000)}k`} />
        </div>

        <div className="bg-white border border-gray-100 rounded-2xl p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Top Products</h2>
          {metrics.top_products.length === 0 ? (
            <p className="text-sm text-gray-400">No sales yet.</p>
          ) : (
            <div className="space-y-3">
              {metrics.top_products.map((p, i) => (
                <div key={p.id} className="flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-xs text-gray-400 w-4">{i + 1}</span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-800 truncate">{p.name}</p>
                      <p className="text-xs text-gray-400">{p.units_sold} sold</p>
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-emerald-600 shrink-0">
                    {formatINR(p.revenue)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="bg-white border border-gray-100 rounded-2xl p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold text-gray-900">Recent Orders</h2>
          <button onClick={onGoToOrders} className="text-xs text-blue-600 font-medium">
            View all
          </button>
        </div>
        {metrics.recent_orders.length === 0 ? (
          <p className="text-sm text-gray-400">No orders yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                  <th className="pb-2 font-medium">Order ID</th>
                  <th className="pb-2 font-medium">Customer</th>
                  <th className="pb-2 font-medium">Items</th>
                  <th className="pb-2 font-medium">Total</th>
                  <th className="pb-2 font-medium">Status</th>
                  <th className="pb-2 font-medium">Time</th>
                </tr>
              </thead>
              <tbody>
                {metrics.recent_orders.map((o) => {
                  const meta = statusMeta(o.status);
                  return (
                    <tr key={o.id} className="border-b border-gray-50 last:border-0">
                      <td className="py-2.5 text-blue-600 font-medium">#{o.id.slice(0, 8)}</td>
                      <td className="py-2.5 text-gray-700">{o.buyer_name || o.buyer_email}</td>
                      <td className="py-2.5 text-gray-500">{o.item_count}</td>
                      <td className="py-2.5 font-medium text-gray-800">{formatINR(o.total_amount)}</td>
                      <td className="py-2.5">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${meta.className}`}>
                          {meta.label}
                        </span>
                      </td>
                      <td className="py-2.5 text-gray-400">{timeAgo(o.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  sub,
  subLabel,
  icon,
  iconBg,
  onClick,
}: {
  label: string;
  value: string;
  sub: React.ReactNode;
  subLabel: string;
  icon: React.ReactNode;
  iconBg: string;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`bg-white border border-gray-100 rounded-2xl p-5 ${onClick ? "cursor-pointer hover:border-gray-200" : ""}`}
    >
      <div className="flex items-start justify-between">
        <p className="text-sm text-gray-500">{label}</p>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${iconBg}`}>{icon}</div>
      </div>
      <p className="text-2xl font-bold text-gray-900 mt-2">{value}</p>
      <p className="mt-1 flex items-center gap-1">
        {sub} <span className="text-xs text-gray-400">{subLabel}</span>
      </p>
    </div>
  );
}

function CoinIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.6" />
      <path d="M10 6.5v7M8 8.2c0-.9.9-1.4 2-1.4s2 .5 2 1.3-.9 1.1-2 1.4c-1.1.3-2 .6-2 1.4s.9 1.3 2 1.3 2-.5 2-1.4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  );
}
function BagIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
      <path d="M4 6h12l-1 10a1.5 1.5 0 0 1-1.5 1.35H6.5A1.5 1.5 0 0 1 5 16L4 6Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M7 6V5a3 3 0 0 1 6 0v1" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}
function AlertIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
      <path d="M10 3.5 17 15.5H3L10 3.5Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M10 8.5v3M10 13.7v.01" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}
function StarIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
      <path d="M10 2.5l2.3 4.7 5.2.75-3.75 3.65.9 5.2L10 14.35 5.35 16.8l.9-5.2L2.5 7.95l5.2-.75L10 2.5Z" />
    </svg>
  );
}
