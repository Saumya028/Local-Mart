"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import SignInPrompt from "@/components/SignInPrompt";

const CART_ICON = (
  <svg viewBox="0 0 24 24" fill="none" className="w-8 h-8">
    <path d="M3 4h2l2.2 10.2a1.5 1.5 0 0 0 1.5 1.2h8.2a1.5 1.5 0 0 0 1.5-1.1L20 8H6.2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    <circle cx="9.5" cy="19.5" r="1.3" fill="currentColor" />
    <circle cx="17" cy="19.5" r="1.3" fill="currentColor" />
  </svg>
);

type CartItem = {
  product: { id: string; name: string; price: string; images: string[] };
  quantity: number;
  subtotal: string;
};

export default function CartPage() {
  const router = useRouter();
  const { loading: authLoading, loggedIn } = useAuth();
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

  // Only ask the backend for the cart once we know there's a signed-in
  // user — otherwise a logged-out visitor just gets a raw 401 error.
  useEffect(() => {
    if (authLoading) return;
    if (!loggedIn) {
      setLoading(false);
      return;
    }
    loadCart();
  }, [authLoading, loggedIn]);

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

  if (authLoading || loading) {
    return (
      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-10">
        <div className="space-y-3 animate-pulse">
          <div className="h-7 w-40 rounded-lg bg-gray-100" />
          <div className="h-16 rounded-2xl bg-gray-100" />
          <div className="h-16 rounded-2xl bg-gray-100" />
        </div>
      </main>
    );
  }

  if (!loggedIn) {
    return (
      <SignInPrompt
        title="Sign in to see your cart"
        description="Log in or create a free account to save items from local shops, check out, and track your orders."
        returnTo="/cart"
        icon={CART_ICON}
      />
    );
  }

  // Signed in but the cart still failed to load (backend down, network
  // blip…) — a calm retry, not a wall of technical text. The raw message
  // stays available for anyone who needs it to report a bug.
  if (error) {
    return (
      <main className="max-w-lg mx-auto px-4 sm:px-6 py-16 text-center space-y-4">
        <h1 className="text-xl font-bold text-gray-900">We couldn&apos;t load your cart</h1>
        <p className="text-sm text-gray-500">Something went wrong on our side. Please try again in a moment.</p>
        <button
          onClick={() => {
            setLoading(true);
            loadCart();
          }}
          className="bg-blue-600 text-white rounded-xl px-6 py-2.5 text-sm font-semibold"
        >
          Try again
        </button>
        <details className="text-xs text-gray-400">
          <summary className="cursor-pointer">Technical details</summary>
          <p className="mt-1 break-words">{error}</p>
        </details>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-10 space-y-6">
      <h1 className="text-2xl font-bold">Your cart</h1>

      {items.length === 0 ? (
        <div className="bg-white border border-gray-100 rounded-3xl px-6 py-12 text-center">
          <div className="mx-auto w-14 h-14 rounded-2xl bg-gray-50 text-gray-400 flex items-center justify-center">
            {CART_ICON}
          </div>
          <p className="mt-4 font-semibold text-gray-900">Your cart is empty</p>
          <p className="mt-1 text-sm text-gray-500">Find something you like from the shops around you.</p>
          <Link
            href="/stores"
            className="mt-6 inline-block bg-blue-600 text-white rounded-xl px-6 py-2.5 text-sm font-semibold"
          >
            Browse stores
          </Link>
        </div>
      ) : (
        <>
          <div className="space-y-4">
            {items.map((item) => (
              <div key={item.product.id} className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
                <div className="flex items-center gap-3 min-w-0">
                  {item.product.images?.[0] ? (
                    // eslint-disable-next-line @next/next/no-img-element -- user-uploaded Supabase Storage URL
                    <img src={item.product.images[0]} alt="" className="w-12 h-12 rounded-md object-cover border border-gray-100 shrink-0" />
                  ) : (
                    <div className="w-12 h-12 rounded-md bg-gray-50 border border-gray-100 shrink-0" />
                  )}
                  <div>
                    <Link href={`/product/${item.product.id}`} className="font-medium hover:underline">
                      {item.product.name}
                    </Link>
                    <p className="text-xs text-gray-400">₹{item.product.price} each</p>
                  </div>
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

          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-4">
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
