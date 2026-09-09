"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch } from "@/lib/apiClient";
import { WishlistEntry } from "./types";

export function WishlistTab({ onLoaded }: { onLoaded?: (items: WishlistEntry[]) => void }) {
  const [items, setItems] = useState<WishlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [addingId, setAddingId] = useState<string | null>(null);

  async function load() {
    try {
      const data: WishlistEntry[] = await apiFetch("/wishlist");
      setItems(data);
      onLoaded?.(data);
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
  }, []);

  async function remove(productId: string) {
    setRemovingId(productId);
    try {
      await apiFetch(`/wishlist/${productId}`, { method: "DELETE" });
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setRemovingId(null);
    }
  }

  async function addToCart(productId: string) {
    setAddingId(productId);
    try {
      await apiFetch("/cart/items", { method: "POST", body: JSON.stringify({ product_id: productId, quantity: 1 }) });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setAddingId(null);
    }
  }

  if (loading) return <p className="text-sm text-gray-400">Loading wishlist…</p>;
  if (error) return <p className="text-sm text-red-500">{error}</p>;
  if (items.length === 0) {
    return (
      <div className="bg-white rounded-2xl border border-gray-100 p-8 text-center">
        <p className="text-sm text-gray-500">Nothing saved yet — tap the heart on a product to add it here.</p>
        <Link href="/search" className="text-sm text-blue-600 underline mt-2 inline-block">
          Browse products
        </Link>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {items.map((entry) => (
        <div key={entry.id} className="bg-white rounded-2xl border border-gray-100 p-4 flex items-center gap-3">
          <Link href={`/product/${entry.product.id}`} className="min-w-0 flex-1">
            <p className="font-medium text-gray-900 text-sm truncate">{entry.product.name}</p>
            <p className="text-xs text-gray-400 truncate">{entry.shop_name}</p>
            <p className="text-sm font-semibold text-gray-800 mt-1">₹{entry.product.price}</p>
            {(!entry.product.is_active || entry.product.stock_qty === 0) && (
              <p className="text-xs text-red-500 mt-0.5">Currently unavailable</p>
            )}
          </Link>
          <div className="flex flex-col gap-1.5 shrink-0">
            <button
              onClick={() => addToCart(entry.product.id)}
              disabled={addingId === entry.product.id || !entry.product.is_active || entry.product.stock_qty === 0}
              className="text-xs font-medium bg-blue-600 text-white rounded-lg px-2.5 py-1.5 disabled:opacity-40 whitespace-nowrap"
            >
              {addingId === entry.product.id ? "Adding…" : "Add to cart"}
            </button>
            <button
              onClick={() => remove(entry.product.id)}
              disabled={removingId === entry.product.id}
              className="text-xs text-red-500 hover:underline disabled:opacity-50"
            >
              Remove
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
