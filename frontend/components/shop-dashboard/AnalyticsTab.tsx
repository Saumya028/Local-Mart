"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { BarChart, LineChart } from "./Charts";
import { Analytics, formatINR } from "./types";

export function AnalyticsTab({ shopId }: { shopId: string }) {
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    apiFetch(`/dashboard/analytics?shop_id=${shopId}`)
      .then(setData)
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [shopId]);

  if (loading) return <p className="text-sm text-gray-400 p-8">Loading analytics…</p>;
  if (error) return <p className="text-sm text-red-500 p-8">{error}</p>;
  if (!data) return null;

  return (
    <div className="p-8 space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <Card label="Total Revenue" value={formatINR(data.total_revenue)} />
        <Card label="Total Orders" value={String(data.total_orders)} />
        <Card label="Unique Customers" value={String(data.unique_customers)} />
        <Card label="Order Success Rate" value={`${data.conversion_rate_pct}%`} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-100 rounded-2xl p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Weekly Orders</h2>
          <BarChart points={data.orders_by_day} />
        </div>
        <div className="bg-white border border-gray-100 rounded-2xl p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Revenue Trend</h2>
          <LineChart points={data.revenue_by_day} formatY={(n) => `₹${Math.round(n / 1000)}k`} />
        </div>
      </div>
    </div>
  );
}

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white border border-gray-100 rounded-2xl p-5">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-2">{value}</p>
    </div>
  );
}
