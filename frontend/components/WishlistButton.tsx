"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/apiClient";

/**
 * Deliberately doesn't check on load whether this product is already
 * wishlisted (that would mean an authenticated GET /wishlist call, and a
 * 401 to quietly swallow, on every single product page view including
 * for logged-out visitors) — starts as an outline heart and just
 * reflects whatever the user does in THIS session. Good enough for a
 * first version; the My Account > Wishlist tab is the source of truth.
 */
export default function WishlistButton({ productId }: { productId: string }) {
  const router = useRouter();
  const [saved, setSaved] = useState(false);
  const [status, setStatus] = useState<"idle" | "saving" | "error">("idle");

  async function toggle() {
    setStatus("saving");
    try {
      if (saved) {
        await apiFetch(`/wishlist/${productId}`, { method: "DELETE" });
        setSaved(false);
      } else {
        await apiFetch("/wishlist", { method: "POST", body: JSON.stringify({ product_id: productId }) });
        setSaved(true);
      }
      setStatus("idle");
    } catch {
      setStatus("error");
    }
  }

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <button
        onClick={toggle}
        disabled={status === "saving"}
        aria-pressed={saved}
        title={saved ? "Remove from wishlist" : "Save to wishlist"}
        className={`w-10 h-10 rounded-full border flex items-center justify-center transition-colors disabled:opacity-50 ${
          saved ? "bg-red-50 border-red-200 text-red-500" : "bg-white border-gray-200 text-gray-400 hover:text-red-400"
        }`}
      >
        <svg viewBox="0 0 20 20" fill={saved ? "currentColor" : "none"} className="w-5 h-5">
          <path
            d="M10 17.3s-6.5-4-8.1-8.1C.9 6.2 2.6 3.5 5.4 3.2c1.6-.2 3.1.6 4 1.9.9-1.3 2.4-2.1 4-1.9 2.8.3 4.5 3 3.5 6-1.6 4.1-6.9 8.1-6.9 8.1Z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {status === "error" && (
        <p className="text-xs text-red-500">
          <button onClick={() => router.push("/login")} className="underline">
            Log in
          </button>{" "}
          to save items.
        </p>
      )}
    </div>
  );
}
