"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { Product, formatINR } from "./types";

function stockBadge(p: Product) {
  if (!p.is_active) return { label: "Inactive", className: "bg-gray-100 text-gray-500" };
  if (p.stock_qty === 0) return { label: "Out of Stock", className: "bg-red-100 text-red-600" };
  if (p.stock_qty <= 15) return { label: "Low Stock", className: "bg-amber-100 text-amber-700" };
  return { label: "Active", className: "bg-emerald-100 text-emerald-700" };
}

export function ProductsTab({ shopId }: { shopId: string }) {
  const [products, setProducts] = useState<Product[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data: Product[] = await apiFetch(`/dashboard/products?shop_id=${shopId}`);
      setProducts(data);
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

  async function toggleActive(product: Product) {
    if (product.is_active) {
      await apiFetch(`/dashboard/products/${product.id}`, { method: "DELETE" });
    } else {
      await apiFetch(`/dashboard/products/${product.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: true }),
      });
    }
    load();
  }

  const filtered = useMemo(() => {
    if (!search.trim()) return products;
    const q = search.toLowerCase();
    return products.filter((p) => p.name.toLowerCase().includes(q) || p.category.toLowerCase().includes(q));
  }, [products, search]);

  return (
    <div className="p-8 space-y-4">
      <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search products…"
          className="w-full sm:w-72 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={() => {
            setEditingId(null);
            setShowForm(!showForm);
          }}
          className="bg-blue-600 text-white text-sm font-medium rounded-lg px-4 py-2 whitespace-nowrap"
        >
          {showForm && !editingId ? "Cancel" : "+ Add Product"}
        </button>
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      {showForm && !editingId && (
        <ProductForm
          shopId={shopId}
          onSaved={() => {
            setShowForm(false);
            load();
          }}
          onCancel={() => setShowForm(false)}
        />
      )}

      <div className="bg-white border border-gray-100 rounded-2xl overflow-hidden">
        {loading ? (
          <p className="text-sm text-gray-400 p-6">Loading products…</p>
        ) : filtered.length === 0 ? (
          <p className="text-sm text-gray-400 p-6">No products yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50/50">
                  <th className="px-5 py-3 font-medium">Product</th>
                  <th className="px-5 py-3 font-medium">Category</th>
                  <th className="px-5 py-3 font-medium">Price</th>
                  <th className="px-5 py-3 font-medium">Stock</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) =>
                  editingId === p.id ? (
                    <tr key={p.id} className="border-b border-gray-50 last:border-0">
                      <td colSpan={6} className="px-5 py-3">
                        <ProductForm
                          shopId={shopId}
                          product={p}
                          onSaved={() => {
                            setEditingId(null);
                            load();
                          }}
                          onCancel={() => setEditingId(null)}
                        />
                      </td>
                    </tr>
                  ) : (
                    <ProductRow
                      key={p.id}
                      product={p}
                      onEdit={() => {
                        setShowForm(false);
                        setEditingId(p.id);
                      }}
                      onToggleActive={() => toggleActive(p)}
                      onStockChange={async (qty) => {
                        await apiFetch(`/dashboard/products/${p.id}`, {
                          method: "PUT",
                          body: JSON.stringify({ stock_qty: qty }),
                        });
                        load();
                      }}
                    />
                  )
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function ProductRow({
  product,
  onEdit,
  onToggleActive,
  onStockChange,
}: {
  product: Product;
  onEdit: () => void;
  onToggleActive: () => void;
  onStockChange: (qty: number) => void;
}) {
  const badge = stockBadge(product);
  return (
    <tr className="border-b border-gray-50 last:border-0 hover:bg-gray-50/40">
      <td className="px-5 py-3">
        <p className="font-medium text-gray-800">{product.name}</p>
      </td>
      <td className="px-5 py-3 text-gray-500">{product.category}</td>
      <td className="px-5 py-3 font-medium text-gray-800">{formatINR(product.price)}</td>
      <td className="px-5 py-3">
        <input
          type="number"
          min={0}
          defaultValue={product.stock_qty}
          onBlur={(e) => {
            const v = Number(e.target.value);
            if (v !== product.stock_qty) onStockChange(v);
          }}
          title="Stock quantity"
          className="w-20 border border-gray-200 rounded-md px-2 py-1 text-sm text-center"
        />
      </td>
      <td className="px-5 py-3">
        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badge.className}`}>{badge.label}</span>
      </td>
      <td className="px-5 py-3">
        <div className="flex items-center gap-3">
          <button onClick={onEdit} className="text-gray-400 hover:text-blue-600" title="Edit">
            <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
              <path d="M4 16l.7-3L13.8 3.9a1.4 1.4 0 0 1 2 0l.3.3a1.4 1.4 0 0 1 0 2L7 15.3 4 16Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
            </svg>
          </button>
          <button
            onClick={onToggleActive}
            className={product.is_active ? "text-gray-400 hover:text-red-500" : "text-gray-400 hover:text-emerald-600"}
            title={product.is_active ? "Deactivate" : "Reactivate"}
          >
            {product.is_active ? (
              <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
                <path d="M5 6h10M8.5 6V4.5h3V6M6 6l.6 9.2A1.4 1.4 0 0 0 8 16.5h4a1.4 1.4 0 0 0 1.4-1.3L14 6" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
              </svg>
            ) : (
              <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
                <path d="M4 10.5 8 14l8-8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </button>
        </div>
      </td>
    </tr>
  );
}

function ProductForm({
  shopId,
  product,
  onSaved,
  onCancel,
}: {
  shopId: string;
  product?: Product;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(product?.name ?? "");
  const [category, setCategory] = useState(product?.category ?? "");
  const [price, setPrice] = useState(product?.price ?? "");
  const [stock, setStock] = useState(String(product?.stock_qty ?? 0));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (product) {
        await apiFetch(`/dashboard/products/${product.id}`, {
          method: "PUT",
          body: JSON.stringify({
            name,
            category,
            price: Number(price),
            stock_qty: Number(stock),
          }),
        });
      } else {
        await apiFetch("/dashboard/products", {
          method: "POST",
          body: JSON.stringify({
            shop_id: shopId,
            name,
            category,
            price: Number(price),
            stock_qty: Number(stock),
          }),
        });
      }
      onSaved();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="border border-gray-100 bg-gray-50 rounded-xl p-4 space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <input
          placeholder="Product name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="border border-gray-200 rounded-md px-3 py-2 text-sm bg-white"
        />
        <input
          placeholder="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          required
          className="border border-gray-200 rounded-md px-3 py-2 text-sm bg-white"
        />
        <input
          placeholder="Price"
          type="number"
          step="0.01"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          required
          className="border border-gray-200 rounded-md px-3 py-2 text-sm bg-white"
        />
        <input
          placeholder="Stock quantity"
          type="number"
          value={stock}
          onChange={(e) => setStock(e.target.value)}
          required
          className="border border-gray-200 rounded-md px-3 py-2 text-sm bg-white"
        />
      </div>
      {error && <p className="text-sm text-red-500">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={saving}
          className="bg-blue-600 text-white rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          {saving ? "Saving…" : product ? "Save changes" : "Add product"}
        </button>
        <button type="button" onClick={onCancel} className="text-sm text-gray-500 px-3 py-2">
          Cancel
        </button>
      </div>
    </form>
  );
}
