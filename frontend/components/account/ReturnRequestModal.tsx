"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { OrderDetailItem, RETURN_REASONS, ReturnRequestType } from "./types";

type ShopProduct = {
  id: string;
  name: string;
  price: string;
  stock_qty: number;
  images: string[];
  variant_attributes: Record<string, string>;
};

/**
 * Opens a return or exchange request for ONE line item of a delivered
 * order — the frontend half of POST /orders/{id}/returns. Rendered from
 * both the account Order list (OrdersTab) and the order tracking page
 * (app/orders/[id]/page.tsx), which is why it takes the order/item as
 * props rather than fetching them itself.
 */
export function ReturnRequestModal({
  orderId,
  shopId,
  item,
  onClose,
  onSubmitted,
}: {
  orderId: string;
  shopId: string;
  item: OrderDetailItem;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const remaining = item.quantity - item.returned_qty;

  const [type, setType] = useState<ReturnRequestType>("return");
  const [quantity, setQuantity] = useState(1);
  const [reason, setReason] = useState(RETURN_REASONS[0]);
  const [comment, setComment] = useState("");
  const [exchangeProducts, setExchangeProducts] = useState<ShopProduct[]>([]);
  const [exchangeProductId, setExchangeProductId] = useState<string | null>(null);
  const selectedExchangeProduct = exchangeProducts.find((p) => p.id === exchangeProductId) ?? null;
  // Purely a preview so the customer isn't surprised later — the backend
  // computes and snapshots the real price_difference itself when the
  // request is actually created (see routers/returns.py's
  // create_return_request), using the product's price at that exact
  // moment, which is the number that ends up governing anything.
  const priceDifferencePreview =
    type === "exchange" && selectedExchangeProduct
      ? (parseFloat(selectedExchangeProduct.price) - parseFloat(item.unit_price)) * quantity
      : null;
  const [loadingProducts, setLoadingProducts] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (type !== "exchange" || exchangeProducts.length > 0) return;
    setLoadingProducts(true);
    apiFetch(`/products?shop_id=${shopId}&limit=50`)
      .then((products: ShopProduct[]) => {
        setExchangeProducts(products.filter((p) => p.id !== item.product_id));
      })
      .catch((err) => setError((err as Error).message))
      .finally(() => setLoadingProducts(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type]);

  async function submit() {
    if (type === "exchange" && !exchangeProductId) {
      setError("Choose a replacement item for the exchange.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await apiFetch(`/orders/${orderId}/returns`, {
        method: "POST",
        body: JSON.stringify({
          order_item_id: item.id,
          request_type: type,
          quantity,
          reason,
          comment: comment.trim() || null,
          exchange_product_id: type === "exchange" ? exchangeProductId : null,
        }),
      });
      onSubmitted();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl w-full max-w-md p-6 space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold text-gray-900">Return or Exchange</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">
            &times;
          </button>
        </div>

        <p className="text-sm text-gray-600">{item.product_name}</p>

        <div className="flex gap-2">
          {(["return", "exchange"] as ReturnRequestType[]).map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium border ${
                type === t ? "bg-blue-600 text-white border-blue-600" : "border-gray-200 text-gray-600"
              }`}
            >
              {t === "return" ? "Return for refund" : "Exchange for another item"}
            </button>
          ))}
        </div>

        <div>
          <label className="text-xs font-medium text-gray-500">Quantity</label>
          <select
            value={quantity}
            onChange={(e) => setQuantity(Number(e.target.value))}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mt-1"
          >
            {Array.from({ length: remaining }, (_, i) => i + 1).map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <p className="text-xs text-gray-400 mt-1">{remaining} of {item.quantity} unit(s) eligible.</p>
        </div>

        <div>
          <label className="text-xs font-medium text-gray-500">Reason</label>
          <select
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mt-1"
          >
            {RETURN_REASONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
        </div>

        {type === "exchange" && (
          <div>
            <label className="text-xs font-medium text-gray-500">Replace with</label>
            {loadingProducts ? (
              <p className="text-xs text-gray-400 mt-1">Loading items…</p>
            ) : exchangeProducts.length === 0 ? (
              <p className="text-xs text-gray-400 mt-1">No other items available from this shop right now.</p>
            ) : (
              <select
                value={exchangeProductId ?? ""}
                onChange={(e) => setExchangeProductId(e.target.value || null)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mt-1"
              >
                <option value="">Select an item…</option>
                {exchangeProducts.map((p) => (
                  <option key={p.id} value={p.id} disabled={p.stock_qty < quantity}>
                    {p.name}
                    {Object.values(p.variant_attributes).length > 0
                      ? ` (${Object.values(p.variant_attributes).join(", ")})`
                      : ""}
                    {p.stock_qty < quantity ? " — out of stock" : ` — ₹${p.price}`}
                  </option>
                ))}
              </select>
            )}
            {priceDifferencePreview !== null && Math.abs(priceDifferencePreview) >= 0.01 && (
              <p
                className={`text-xs mt-2 rounded-lg px-3 py-2 ${
                  priceDifferencePreview > 0
                    ? "bg-amber-50 text-amber-700"
                    : "bg-emerald-50 text-emerald-700"
                }`}
              >
                {priceDifferencePreview > 0
                  ? `This item costs ₹${priceDifferencePreview.toFixed(2)} more — you'll be asked to pay the difference once the shop approves the exchange.`
                  : `This item costs ₹${Math.abs(priceDifferencePreview).toFixed(2)} less — the shop will refund the difference once the exchange is completed.`}
              </p>
            )}
          </div>
        )}

        <div>
          <label className="text-xs font-medium text-gray-500">Additional details (optional)</label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm mt-1"
            placeholder="Tell the shop anything else that would help…"
          />
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex gap-2 pt-2">
          <button
            onClick={onClose}
            className="flex-1 py-2 rounded-lg text-sm font-medium border border-gray-200 text-gray-600"
          >
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={submitting || remaining < 1}
            className="flex-1 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white disabled:opacity-50"
          >
            {submitting ? "Submitting…" : "Submit request"}
          </button>
        </div>
      </div>
    </div>
  );
}
