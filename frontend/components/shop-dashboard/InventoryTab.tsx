"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { Product } from "./types";

const LOW_STOCK_THRESHOLD = 15;

export function InventoryTab({ shopId }: { shopId: string }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data: Product[] = await apiFetch(`/dashboard/products?shop_id=${shopId}`);
      setProducts(data.filter((p) => p.is_active));
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopId]);

  async function restock(product: Product, addQty = 20) {
    setSavingId(product.id);
    try {
      await apiFetch(`/dashboard/products/${product.id}`, {
        method: "PUT",
        body: JSON.stringify({ stock_qty: product.stock_qty + addQty }),
      });
      await load();
    } finally {
      setSavingId(null);
    }
  }

  if (loading) return <p className="text-sm text-gray-400 p-8">Loading inventory…</p>;
  if (error) return <p className="text-sm text-red-500 p-8">{error}</p>;

  const totalSkus = products.length;
  const lowStock = products.filter((p) => p.stock_qty > 0 && p.stock_qty <= LOW_STOCK_THRESHOLD);
  const outOfStock = products.filter((p) => p.stock_qty === 0);
  const maxStock = Math.max(...products.map((p) => p.stock_qty), 1);

  return (
    <div className="p-8 space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Total SKUs" value={String(totalSkus)} tone="blue" />
        <StatCard label="Low Stock Items" value={String(lowStock.length)} sub="Needs attention" tone="amber" />
        <StatCard label="Out of Stock" value={String(outOfStock.length)} sub="Update needed" tone="red" />
      </div>

      <div className="bg-white border border-gray-100 rounded-2xl p-5">
        <h2 className="font-semibold text-gray-900 mb-4">Stock Levels</h2>
        {products.length === 0 ? (
          <p className="text-sm text-gray-400">No active products yet.</p>
        ) : (
          <div className="space-y-4">
            {products
              .slice()
              .sort((a, b) => a.stock_qty - b.stock_qty)
              .map((p) => {
                const pct = Math.min(100, (p.stock_qty / maxStock) * 100);
                const barColor = p.stock_qty === 0 ? "bg-gray-200" : p.stock_qty <= LOW_STOCK_THRESHOLD ? "bg-amber-400" : "bg-emerald-500";
                return (
                  <div key={p.id} className="flex items-center gap-4">
                    <p className="w-48 shrink-0 text-sm font-medium text-gray-700 truncate">{p.name}</p>
                    <div className="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden">
                      <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
                    </div>
                    <span
                      className={`w-20 shrink-0 text-sm text-right ${
                        p.stock_qty === 0 ? "text-red-500 font-medium" : "text-gray-600"
                      }`}
                    >
                      {p.stock_qty} units
                    </span>
                    {p.stock_qty <= LOW_STOCK_THRESHOLD && (
                      <button
                        onClick={() => restock(p)}
                        disabled={savingId === p.id}
                        className="shrink-0 text-xs font-medium border border-gray-200 rounded-md px-3 py-1.5 hover:bg-gray-50 disabled:opacity-50"
                      >
                        {savingId === p.id ? "…" : "Restock +20"}
                      </button>
                    )}
                  </div>
                );
              })}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone: "blue" | "amber" | "red";
}) {
  const iconBg = { blue: "bg-blue-50 text-blue-600", amber: "bg-amber-50 text-amber-600", red: "bg-red-50 text-red-600" }[tone];
  return (
    <div className="bg-white border border-gray-100 rounded-2xl p-5">
      <div className="flex items-start justify-between">
        <p className="text-sm text-gray-500">{label}</p>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${iconBg}`}>
          <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
            <path d="M10 2 3 5.5v9L10 18l7-3.5v-9L10 2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
          </svg>
        </div>
      </div>
      <p className="text-2xl font-bold text-gray-900 mt-2">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}
