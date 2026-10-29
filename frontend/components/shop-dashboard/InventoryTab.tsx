"use client";

import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { Product } from "./types";

type Filter = "all" | "low" | "out";

/**
 * Stock levels with the SAME alert rules the notifications use: a product is
 * "low" at/below its own alert level (or the shop default), "out" at zero.
 * Those come from the server (`stock_status`, `effective_low_stock_threshold`)
 * — nothing is hard-coded here.
 */
export function InventoryTab({ shopId }: { shopId: string }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");

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

  const low = useMemo(() => products.filter((p) => p.stock_status === "low"), [products]);
  const out = useMemo(() => products.filter((p) => p.stock_status === "out"), [products]);
  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return products
      .filter((p) => (filter === "all" ? true : p.stock_status === filter))
      .filter((p) => !q || p.name.toLowerCase().includes(q) || (p.sku ?? "").toLowerCase().includes(q) || (p.barcode ?? "") === search.trim())
      .sort((a, b) => a.stock_qty - b.stock_qty);
  }, [products, filter, search]);

  if (loading) return <p className="text-sm text-gray-400 p-4 sm:p-8">Loading inventory…</p>;
  if (error) return <p className="text-sm text-red-500 p-4 sm:p-8">{error}</p>;

  const maxStock = Math.max(...products.map((p) => p.stock_qty), 1);

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Active products" value={String(products.length)} tone="blue" onClick={() => setFilter("all")} active={filter === "all"} />
        <StatCard label="Low stock" value={String(low.length)} sub="At or below alert level" tone="amber" onClick={() => setFilter("low")} active={filter === "low"} />
        <StatCard label="Out of stock" value={String(out.length)} sub="Customers can’t order these" tone="red" onClick={() => setFilter("out")} active={filter === "out"} />
      </div>

      <div className="bg-white border border-gray-100 rounded-2xl p-4 sm:p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <h2 className="font-semibold text-gray-900">
            Stock levels{filter !== "all" && <span className="text-gray-400 font-normal"> · {filter === "low" ? "low stock" : "out of stock"}</span>}
          </h2>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Name, SKU or barcode…"
            className="w-full sm:w-64 border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
          />
        </div>
        {visible.length === 0 ? (
          <p className="text-sm text-gray-400">
            {products.length === 0 ? "No active products yet." : filter === "all" ? "No products match." : "Nothing here — you’re well stocked."}
          </p>
        ) : (
          <div className="space-y-4">
            {visible.map((p) => {
              const pct = Math.min(100, (p.stock_qty / maxStock) * 100);
              const barColor = p.stock_status === "out" ? "bg-gray-200" : p.stock_status === "low" ? "bg-amber-400" : "bg-emerald-500";
              return (
                <div key={p.id} className="flex flex-wrap sm:flex-nowrap items-center gap-x-4 gap-y-1.5">
                  <div className="w-full sm:w-52 sm:shrink-0 min-w-0">
                    <p className="text-sm font-medium text-gray-700 truncate">
                      {p.name}
                      {p.unit_label && <span className="text-gray-400 font-normal"> · {p.unit_label}</span>}
                    </p>
                    {p.sku && <p className="text-[11px] text-gray-400">SKU {p.sku}</p>}
                  </div>
                  <div className="flex-1 min-w-[80px] h-2 rounded-full bg-gray-100 overflow-hidden">
                    <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
                  </div>
                  <span className={`w-24 shrink-0 text-sm text-right ${p.stock_status === "out" ? "text-red-500 font-medium" : "text-gray-600"}`}>
                    {p.stock_qty} units
                  </span>
                  <span className="w-20 shrink-0 text-[11px] text-gray-400 text-right">alert ≤ {p.effective_low_stock_threshold ?? "–"}</span>
                  {p.stock_status !== "ok" && (
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
        <p className="text-[11px] text-gray-400 mt-5">
          You’re notified once when a product drops to its alert level and once when it sells out. Change the default in Store settings, or set a
          level per product when editing it.
        </p>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  tone,
  onClick,
  active,
}: {
  label: string;
  value: string;
  sub?: string;
  tone: "blue" | "amber" | "red";
  onClick: () => void;
  active: boolean;
}) {
  const iconBg = { blue: "bg-blue-50 text-blue-600", amber: "bg-amber-50 text-amber-600", red: "bg-red-50 text-red-600" }[tone];
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`text-left bg-white border rounded-2xl p-4 sm:p-5 transition ${active ? "border-blue-300 ring-1 ring-blue-200" : "border-gray-100 hover:border-gray-200"}`}
    >
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
    </button>
  );
}
