type ShopInfo = { id: string; name: string; category: string; rating: number };

type AttributeField = { key: string; label: string; type: string };

type VariantSummary = {
  id: string;
  variant_attributes: Record<string, string>;
  price: string;
  stock_qty: number;
  is_active: boolean;
  thumbnail: string | null;
};

type ProductDetail = {
  id: string;
  name: string;
  description: string | null;
  price: string;
  category: string;
  stock_qty: number;
  attributes: Record<string, unknown>;
  images: string[];
  variant_attributes: Record<string, string>;
  variants: VariantSummary[];
  shop: ShopInfo | null;
};

import Link from "next/link";
import AddToCartButton from "@/components/AddToCartButton";
import WishlistButton from "@/components/WishlistButton";
import { ProductGallery } from "@/components/ProductGallery";
import { VariantPicker } from "@/components/VariantPicker";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getProduct(id: string): Promise<ProductDetail | null> {
  try {
    // revalidate: 30 -> product pages are read far more than written, and
    // this matches the backend's own Redis cache TTL for the same
    // endpoint (60s) closely enough that the two layers stay in sync.
    const res = await fetch(`${API_URL}/products/${id}`, { next: { revalidate: 30 } });
    if (!res.ok) return null;
    const data = await res.json();
    // Defensive: a response served from a cache entry written before
    // variants existed on this product (60s Redis TTL on the backend)
    // may be missing this field entirely — never trust it unconditionally.
    return { ...data, variants: data.variants ?? [], images: data.images ?? [] };
  } catch {
    return null;
  }
}

async function getAttributeLabels(category: string): Promise<Record<string, string>> {
  // Best-effort only — falls back to showing the raw attribute key if
  // this fails or the category has no schema, same as before this was
  // added. Never worth failing the whole product page over.
  try {
    const res = await fetch(`${API_URL}/attribute-schemas/product/${encodeURIComponent(category)}`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return {};
    const data: { fields: AttributeField[] } = await res.json();
    return Object.fromEntries(data.fields.map((f) => [f.key, f.label]));
  } catch {
    return {};
  }
}

export default async function ProductPage({ params }: { params: { id: string } }) {
  const product = await getProduct(params.id);

  if (!product) {
    return (
      <main className="max-w-3xl mx-auto px-6 py-10">
        <p className="text-gray-500">Product not found.</p>
      </main>
    );
  }

  // Shared specs (brand, warranty, composition, etc.) — what's DIFFERENT
  // about this specific variant (color, weight) is shown separately via
  // VariantPicker below, not mixed into this list.
  const attributeEntries = Object.entries(product.attributes || {}).filter(
    ([, value]) => value !== "" && value !== null
  );
  const labels = attributeEntries.length > 0 ? await getAttributeLabels(product.category) : {};
  const variantSummary = Object.entries(product.variant_attributes || {})
    .map(([k, v]) => `${k}: ${v}`)
    .join(", ");

  return (
    <main className="max-w-5xl mx-auto px-6 py-10">
      <div className="grid md:grid-cols-2 gap-10">
        <ProductGallery images={product.images} alt={product.name} />

        <div className="space-y-4">
          <div>
            <p className="text-xs text-gray-400">{product.category}</p>
            <h1 className="text-2xl font-bold">{product.name}</h1>
            {variantSummary && <p className="text-sm text-gray-500 mt-0.5">{variantSummary}</p>}
          </div>

          <p className="text-2xl font-semibold">₹{product.price}</p>

          {product.description && <p className="text-gray-600 text-sm">{product.description}</p>}

          {(product.variants?.length ?? 0) > 0 && (
            <VariantPicker currentId={product.id} variants={product.variants} />
          )}

          <p className="text-sm text-gray-400">
            {product.stock_qty > 0 ? `${product.stock_qty} in stock` : "Out of stock"}
          </p>

          <div className="flex items-center gap-3">
            <AddToCartButton productId={product.id} inStock={product.stock_qty > 0} />
            <WishlistButton productId={product.id} />
          </div>

          {product.shop && (
            <div className="border-t pt-4 mt-2">
              <p className="text-sm text-gray-500">
                Sold by{" "}
                <Link href={`/store/${product.shop.id}`} className="font-medium text-blue-600 hover:underline">
                  {product.shop.name}
                </Link>{" "}
                · ★ {product.shop.rating.toFixed(1)}
              </p>
            </div>
          )}

          {attributeEntries.length > 0 && (
            <div className="border-t pt-4">
              <p className="text-sm font-medium text-gray-900 mb-2">Item details</p>
              <dl className="text-sm text-gray-600 grid grid-cols-[auto,1fr] gap-x-4 gap-y-1.5">
                {attributeEntries.map(([key, value]) => (
                  <div key={key} className="contents">
                    <dt className="text-gray-400">{labels[key] ?? key}</dt>
                    <dd className="text-gray-700">
                      {typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
