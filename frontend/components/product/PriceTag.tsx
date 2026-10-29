import { inr } from "@/lib/shopInfo";

export type PriceFields = {
  price: string | number;
  mrp?: string | number | null;
  discount_percent?: number | null;
  unit_label?: string | null;
  unit_price_label?: string | null;
  stock_qty?: number;
};

/**
 * One consistent way to show what something costs:
 *   ₹80  ₹100(struck)  [20% off]
 *   500 g · ₹16 / 100 g      (large size only shows the comparison price)
 *   Only 3 left / Out of stock
 * `price` is always what the customer pays; MRP is only shown when it's a
 * real discount (the backend sends discount_percent only then).
 */
export function PriceTag({
  p,
  size = "sm",
  showStock = true,
  className = "",
}: {
  p: PriceFields;
  size?: "sm" | "lg";
  showStock?: boolean;
  className?: string;
}) {
  const discounted = p.discount_percent != null && p.discount_percent > 0 && p.mrp != null;
  const stock = p.stock_qty;
  return (
    <div className={className}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <span className={size === "lg" ? "text-2xl font-semibold text-gray-900" : "text-sm font-semibold text-gray-900"}>
          {inr(p.price)}
        </span>
        {discounted && (
          <>
            <span className={`${size === "lg" ? "text-base" : "text-xs"} text-gray-400 line-through`}>{inr(p.mrp)}</span>
            <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50 rounded px-1.5 py-0.5">
              {p.discount_percent}% off
            </span>
          </>
        )}
      </div>
      {(p.unit_label || (size === "lg" && p.unit_price_label)) && (
        <p className="text-xs text-gray-500 mt-0.5">
          {p.unit_label}
          {size === "lg" && p.unit_price_label ? `${p.unit_label ? " · " : ""}${p.unit_price_label}` : ""}
        </p>
      )}
      {showStock && stock !== undefined && stock <= 0 && <p className="text-xs text-red-500 mt-0.5">Out of stock</p>}
      {showStock && stock !== undefined && stock > 0 && stock <= 5 && (
        <p className="text-xs text-amber-600 mt-0.5">Only {stock} left</p>
      )}
    </div>
  );
}
