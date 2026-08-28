"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/apiClient";

type CartItem = {
  product: { id: string; name: string; price: string };
  quantity: number;
  subtotal: string;
};

export default function CartPage() {
  const router = useRouter();
  const [items, setItems] = useState<CartItem[]>([]);
  const [total, setTotal] = useState("0.00");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadCart() {
    try {
      const data = await apiFetch("/cart");
      setItems(data.items);
      setTotal(data.total);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCart();
  }, []);

  async function updateQuantity(productId: string, quantity: number) {
    await apiFetch(`/cart/items/${productId}`, {
      method: "PUT",
      body: JSON.stringify({ quantity }),
    });
    loadCart();
  }

  async function removeItem(productId: string) {
    await apiFetch(`/cart/items/${productId}`, { method: "DELETE" });
    loadCart();
  }

  if (loading) {
    return (
      <main className="max-w-3xl mx-auto px-6 py-10">
        <p className="text-sm text-gray-400">Loading cart…</p>
      </main>
    );
  }

  if (error) {
    return (
      <main className="max-w-3xl mx-auto px-6 py-10 space-y-3">
        <p className="text-sm text-red-500">Couldn&apos;t load your cart: {error}</p>
        <Link href="/login" className="text-blue-600 underline text-sm">
          Log in
        </Link>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto px-6 py-10 space-y-6">
      <h1 className="text-2xl font-bold">Your cart</h1>

      {items.length === 0 ? (
        <p className="text-sm text-gray-400">
          Your cart is empty.{" "}
          <Link href="/" className="underline">
            Browse products
          </Link>
          .
        </p>
      ) : (
        <>
          <div className="space-y-4">
            {items.map((item) => (
              <div key={item.product.id} className="flex items-center justify-between border-b pb-4">
                <div>
                  <Link href={`/product/${item.product.id}`} className="font-medium hover:underline">
                    {item.product.name}
                  </Link>
                  <p className="text-xs text-gray-400">₹{item.product.price} each</p>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    type="number"
                    min={0}
                    value={item.quantity}
                    onChange={(e) => updateQuantity(item.product.id, Number(e.target.value))}
                    className="w-16 border rounded-md px-2 py-1 text-sm text-center"
                  />
                  <p className="w-20 text-right text-sm font-medium">₹{item.subtotal}</p>
                  <button
                    onClick={() => removeItem(item.product.id)}
                    className="text-xs text-red-500 underline"
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between pt-4">
            <p className="text-lg font-semibold">Total: ₹{total}</p>
            <button
              onClick={() => router.push("/checkout")}
              className="bg-blue-600 text-white rounded-md px-6 py-2 text-sm font-medium"
            >
              Proceed to checkout
            </button>
          </div>
        </>
      )}
    </main>
  );
}
