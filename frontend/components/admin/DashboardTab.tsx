"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { LineChart, DonutChart } from "./Charts";
import {
  AdminShop,
  CategoryShare,
  DashboardSummary,
  MonthPoint,
  categoryColor,
  formatINR,
  docsStatusMeta,
} from "./types";

function ChangeBadge({ pct }: { pct: number | null }) {
  if (pct === null) return null;
  const positive = pct >= 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-medium ${positive ? "text-emerald-600" : "text-red-600"}`}>
      {positive ? "↑" : "↓"} {Math.abs(pct)}%
    </span>
  );
}

const CARD_ICONS: Record<string, JSX.Element> = {
  shops: (
    <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5 text-blue-600">
      <path d="M3 7.5 4 3h12l1 4.5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M4 8.2V17h12V8.2" stroke="currentColor" strokeWidth="1.6" />
      <path d="M8 17v-4.5h4V17" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  users: (
    <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5 text-emerald-600">
      <circle cx="10" cy="7" r="3" stroke="currentColor" strokeWidth="1.6" />
      <path d="M3.5 17c0-3 3-5 6.5-5s6.5 2 6.5 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  orders: (
    <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5 text-violet-600">
      <path d="M4 6h12l-1 10a1.5 1.5 0 0 1-1.5 1.35H6.5A1.5 1.5 0 0 1 5 16L4 6Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M7 6V5a3 3 0 0 1 6 0v1" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  ),
  revenue: (
    <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5 text-amber-600">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.6" />
      <path d="M10 6v8M12.3 8.2c0-1-1-1.7-2.3-1.7s-2.3.6-2.3 1.6c0 2.2 4.6 1.1 4.6 3.2 0 1-1 1.7-2.3 1.7s-2.3-.7-2.3-1.7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  ),
};

export function DashboardTab({
  onGoToShops,
  onPendingCountChange,
}: {
  onGoToShops: () => void;
  onPendingCountChange?: (n: number) => void;
}) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [trend, setTrend] = useState<MonthPoint[]>([]);
  const [categories, setCategories] = useState<CategoryShare[]>([]);
  const [pending, setPending] = useState<AdminShop[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actingId, setActingId] = useState<string | null>(null);

  async function loadAll() {
    try {
      const [s, t, c, p] = await Promise.all([
        apiFetch("/admin/dashboard-summary"),
        apiFetch("/admin/revenue-trend?months=7"),
        apiFetch("/admin/category-breakdown"),
        apiFetch("/admin/shops?approval_status=pending"),
      ]);
      setSummary(s);
      setTrend(t);
      setCategories(c);
      setPending(p.slice(0, 4));
      onPendingCountChange?.(p.length);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function act(shop: AdminShop, action: "approve" | "reject") {
    let reason: string | null = null;
    if (action === "reject") {
      reason = window.prompt(`Reason for rejecting "${shop.name}"? (shown to the owner, optional)`) ?? null;
      if (reason === null) return;
    }

    setActingId(shop.id);
    try {
      await apiFetch(`/admin/shops/${shop.id}/${action}`, {
        method: "PATCH",
        body: reason !== null ? JSON.stringify({ reason: reason || null }) : undefined,
      });
      await loadAll();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setActingId(null);
    }
  }

  if (loading) return <div className="p-8"><p className="text-sm text-gray-400">Loading…</p></div>;
  if (error) return <div className="p-8"><p className="text-sm text-red-500">{error}</p></div>;
  if (!summary) return null;

  const totalRevenue = trend.reduce((sum, p) => sum + Number(p.value), 0);
  const yearLabel = new Date().getFullYear();

  const cards = [
    {
      key: "shops",
      label: "Total Shops",
      value: summary.total_shops.toLocaleString("en-IN"),
      delta: `↑ ${summary.shops_added_this_month} this month`,
    },
    {
      key: "users",
      label: "Total Users",
      value: summary.total_users.toLocaleString("en-IN"),
      delta: `↑ ${summary.users_added_this_week.toLocaleString("en-IN")} this week`,
    },
    {
      key: "orders",
      label: "Monthly Orders",
      value: summary.monthly_orders.toLocaleString("en-IN"),
      delta:
        summary.monthly_orders_change_pct === null
          ? "No data for last month"
          : `${summary.monthly_orders_change_pct >= 0 ? "↑" : "↓"} ${Math.abs(summary.monthly_orders_change_pct)}% vs last month`,
    },
    {
      key: "revenue",
      label: "Platform Revenue",
      value: formatINR(summary.platform_revenue, { compact: true }),
      delta:
        summary.platform_revenue_change_pct === null
          ? "No data for last month"
          : `${summary.platform_revenue_change_pct >= 0 ? "↑" : "↓"} ${Math.abs(summary.platform_revenue_change_pct)}% this month`,
    },
  ];

  return (
    <div className="p-8 space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5">
        {cards.map((c) => (
          <div key={c.key} className="bg-white rounded-2xl border border-gray-100 p-5">
            <div className="flex items-start justify-between">
              <p className="text-sm text-gray-500">{c.label}</p>
              <div className="w-9 h-9 rounded-lg bg-gray-50 flex items-center justify-center">{CARD_ICONS[c.key]}</div>
            </div>
            <p className="text-2xl font-bold text-gray-900 mt-2">{c.value}</p>
            <p className="text-xs text-emerald-600 mt-1">{c.delta}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div className="xl:col-span-2 bg-white rounded-2xl border border-gray-100 p-6">
          <div className="flex items-start justify-between mb-1">
            <div>
              <h3 className="font-semibold text-gray-900">Platform Revenue</h3>
              <p className="text-xs text-gray-400">
                {formatINR(totalRevenue, { compact: true })} total in {yearLabel}
              </p>
            </div>
            {summary.platform_revenue_change_pct !== null && (
              <span className="text-xs font-medium bg-emerald-50 text-emerald-600 rounded-full px-2.5 py-1">
                {summary.platform_revenue_change_pct >= 0 ? "↑" : "↓"} {Math.abs(summary.platform_revenue_change_pct)}% MoM
              </span>
            )}
          </div>
          <LineChart points={trend} formatY={(n) => formatINR(n, { compact: true })} />
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Orders by Category</h3>
          {categories.length === 0 ? (
            <p className="text-sm text-gray-400">No confirmed orders yet.</p>
          ) : (
            <div className="flex flex-col items-center gap-4">
              <DonutChart shares={categories} size={180} />
              <div className="w-full space-y-2">
                {categories.map((c, i) => (
                  <div key={c.category} className="flex items-center justify-between text-sm">
                    <span className="flex items-center gap-2 text-gray-600">
                      <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: categoryColor(c.category, i) }} />
                      {c.category}
                    </span>
                    <span className="font-medium text-gray-800">{c.pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-gray-100 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            Pending Shop Approvals
            {pending.length > 0 && (
              <span className="bg-amber-100 text-amber-700 text-xs font-semibold rounded-full px-2 py-0.5">{pending.length}</span>
            )}
          </h3>
          <button onClick={onGoToShops} className="text-sm text-blue-600 hover:underline">
            View all
          </button>
        </div>
        {pending.length === 0 ? (
          <p className="text-sm text-gray-400">No shops waiting on approval.</p>
        ) : (
          <div className="divide-y divide-gray-50">
            {pending.map((shop) => (
              <div key={shop.id} className="flex items-center justify-between py-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600 shrink-0">
                    <svg viewBox="0 0 20 20" fill="none" className="w-4.5 h-4.5">
                      <path d="M3 7.5 4 3h12l1 4.5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
                      <path d="M4 8.2V17h12V8.2" stroke="currentColor" strokeWidth="1.6" />
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{shop.name}</p>
                    <p className="text-xs text-gray-400 truncate">
                      {shop.owner_name ?? shop.owner_email} · {shop.category}
                      {shop.location ? ` · ${shop.location}` : ""}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span
                    className={`text-xs font-medium rounded-full px-2.5 py-1 ${docsStatusMeta(shop.docs_status).className}`}
                  >
                    {docsStatusMeta(shop.docs_status).label}
                  </span>
                  <button
                    onClick={() => act(shop, "approve")}
                    disabled={actingId === shop.id}
                    className="text-xs font-medium bg-emerald-500 text-white rounded-lg px-3 py-1.5 hover:bg-emerald-600 disabled:opacity-50"
                  >
                    ✓ Approve
                  </button>
                  <button
                    onClick={() => act(shop, "reject")}
                    disabled={actingId === shop.id}
                    className="text-xs font-medium border border-gray-200 text-red-600 rounded-lg px-3 py-1.5 hover:bg-red-50 disabled:opacity-50"
                  >
                    ✕ Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
