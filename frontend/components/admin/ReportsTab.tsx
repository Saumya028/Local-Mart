"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { BarChart, DonutChart } from "./Charts";
import { CategoryShare, MonthPoint, categoryColor } from "./types";

export function ReportsTab() {
  const [growth, setGrowth] = useState<MonthPoint[]>([]);
  const [categories, setCategories] = useState<CategoryShare[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([apiFetch("/admin/shop-growth?months=7"), apiFetch("/admin/category-breakdown")])
      .then(([g, c]) => {
        setGrowth(g);
        setCategories(c);
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8"><p className="text-sm text-gray-400">Loading…</p></div>;
  if (error) return <div className="p-8"><p className="text-sm text-red-500">{error}</p></div>;

  return (
    <div className="p-8">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
        <div className="bg-white rounded-2xl border border-gray-100 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Monthly Shop Growth</h3>
          {growth.every((p) => Number(p.value) === 0) ? (
            <p className="text-sm text-gray-400">No shops created in this period yet.</p>
          ) : (
            <BarChart points={growth} />
          )}
        </div>

        <div className="bg-white rounded-2xl border border-gray-100 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Revenue by Category</h3>
          {categories.length === 0 ? (
            <p className="text-sm text-gray-400">No confirmed orders yet.</p>
          ) : (
            <div className="flex flex-col items-center gap-4">
              <DonutChart shares={categories} size={200} />
              <div className="flex flex-wrap items-center justify-center gap-x-4 gap-y-1.5">
                {categories.map((c, i) => (
                  <span key={c.category} className="flex items-center gap-1.5 text-sm text-gray-600">
                    <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: categoryColor(c.category, i) }} />
                    {c.category} <span className="font-medium text-gray-800">{c.pct}%</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
