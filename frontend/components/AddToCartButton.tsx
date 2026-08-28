"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/apiClient";

/**
 * Pulled out into its own small Client Component rather than making the
 * whole Product Detail page client-rendered — that page's data-fetching
 * (price, description, stock) has no reason to leave the server; only
 * this one button needs interactivity and the auth token.
 */
export default function AddToCartButton({
  productId,
  inStock,
}: {
  productId: string;
  inStock: boolean;
}) {
  const router = useRouter();
  const [status, setStatus] = useState<"idle" | "adding" | "added" | "error">("idle");

  async function handleClick() {
    setStatus("adding");
    try {
      await apiFetch("/cart/items", {
        method: "POST",
        body: JSON.stringify({ product_id: productId, quantity: 1 }),
      });
      setStatus("added");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="space-y-2">
      <button
        onClick={handleClick}
        disabled={!inStock || status === "adding"}
        className="bg-blue-600 text-white rounded-md px-6 py-2 text-sm font-medium disabled:opacity-40"
      >
        {status === "adding" ? "Adding…" : status === "added" ? "Added ✓" : "Add to cart"}
      </button>

      {status === "added" && (
        <p className="text-xs text-gray-500">
          <button onClick={() => router.push("/cart")} className="underline">
            View cart
          </button>
        </p>
      )}

      {status === "error" && (
        <p className="text-xs text-red-500">
          Couldn&apos;t add to cart —{" "}
          <button onClick={() => router.push("/login")} className="underline">
            log in
          </button>{" "}
          first.
        </p>
      )}
    </div>
  );
}
