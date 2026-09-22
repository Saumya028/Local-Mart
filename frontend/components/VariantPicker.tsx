"use client";

import Link from "next/link";

type Variant = {
  id: string;
  variant_attributes: Record<string, string>;
  is_active: boolean;
  thumbnail: string | null;
};

/**
 * Renders one pill per sibling in the variant_group_id family (see
 * routers/products.py's GET /products/{id}) — clicking navigates to
 * that sibling's own product page, since each variant is a fully
 * independent product row (own id, price, stock — see migration 0011's
 * docstring for why). The current product is highlighted; an
 * out-of-stock-but-still-listed sibling is shown struck through rather
 * than hidden, same as Amazon's "Currently unavailable" swatch.
 */
export function VariantPicker({ currentId, variants }: { currentId: string; variants: Variant[] }) {
  // Most sellers set one key per product (see the dashboard's Variant
  // form), so this is usually just "Color" — but nothing enforces
  // uniform keys across siblings, so fall back to showing the whole
  // key:value pairing on the pill when it doesn't look like a single
  // shared attribute.
  const keys = Array.from(new Set(variants.flatMap((v) => Object.keys(v.variant_attributes))));
  const singleSharedKey = keys.length === 1 ? keys[0] : null;

  return (
    <div className="space-y-1.5">
      {singleSharedKey && <p className="text-xs font-medium text-gray-500">{singleSharedKey}</p>}
      <div className="flex flex-wrap gap-2">
        {variants.map((v) => {
          const label = singleSharedKey
            ? v.variant_attributes[singleSharedKey] ?? "—"
            : Object.entries(v.variant_attributes)
                .map(([k, val]) => `${k}: ${val}`)
                .join(", ") || "Option";
          const isCurrent = v.id === currentId;
          return (
            <Link
              key={v.id}
              href={`/product/${v.id}`}
              className={`flex items-center gap-1.5 border rounded-lg px-3 py-1.5 text-sm transition ${
                isCurrent
                  ? "border-blue-500 ring-1 ring-blue-500 text-blue-700 bg-blue-50"
                  : v.is_active
                  ? "border-gray-200 hover:border-gray-400 text-gray-700"
                  : "border-gray-100 text-gray-300 line-through pointer-events-none"
              }`}
            >
              {v.thumbnail && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={v.thumbnail} alt="" className="w-5 h-5 rounded object-cover" />
              )}
              {label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
