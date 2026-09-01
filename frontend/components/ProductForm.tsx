"use client";

import { FormEvent, useState } from "react";
import { apiFetch } from "@/lib/apiClient";

type ProductFormValues = {
  name: string;
  description: string;
  price: string;
  category: string;
  stock_qty: string;
};

export default function ProductForm({
  initial,
  productId,
  onSaved,
  onCancel,
}: {
  initial?: Partial<ProductFormValues>;
  /** If provided, this edits an existing product (PUT); otherwise creates
   * a new one (POST). One form, two modes — avoids duplicating the same
   * fields and validation in two places. */
  productId?: string;
  onSaved: () => void;
  onCancel?: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [price, setPrice] = useState(initial?.price ?? "");
  const [category, setCategory] = useState(initial?.category ?? "");
  const [stockQty, setStockQty] = useState(initial?.stock_qty ?? "0");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const payload = {
      name,
      description: description || null,
      price: Number(price),
      category,
      stock_qty: Number(stockQty),
    };

    try {
      if (productId) {
        await apiFetch(`/dashboard/products/${productId}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await apiFetch("/dashboard/products", {
          method: "POST",
          body: JSON.stringify(payload),
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
    <form onSubmit={handleSubmit} className="space-y-3 border rounded-lg p-4">
      <div className="grid grid-cols-2 gap-3">
        <input
          placeholder="Product name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className="border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          placeholder="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          required
          className="border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      <textarea
        placeholder="Description (optional)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={2}
        className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />

      <div className="grid grid-cols-2 gap-3">
        <input
          type="number"
          step="0.01"
          min="0"
          placeholder="Price"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          required
          className="border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          type="number"
          min="0"
          placeholder="Stock quantity"
          value={stockQty}
          onChange={(e) => setStockQty(e.target.value)}
          required
          className="border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {error && <p className="text-sm text-red-500">{error}</p>}

      <div className="flex gap-3">
        <button
          type="submit"
          disabled={saving}
          className="bg-blue-600 text-white rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          {saving ? "Saving…" : productId ? "Save changes" : "Add product"}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className="text-sm text-gray-500 underline">
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
