type ShopInfo = { id: string; name: string; category: string; rating: number };

type AttributeField = { key: string; label: string; type: string };

type ProductDetail = {
  id: string;
  name: string;
  description: string | null;
  price: string;
  category: string;
  stock_qty: number;
  attributes: Record<string, unknown>;
  shop: ShopInfo | null;
};

import Link from "next/link";
import AddToCartButton from "@/components/AddToCartButton";
import WishlistButton from "@/components/WishlistButton";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getProduct(id: string): Promise<ProductDetail | null> {
  try {
    // revalidate: 30 -> product pages are read far more than written, and
    // this matches the backend's own Redis cache TTL for the same
    // endpoint (60s) closely enough that the two layers stay in sync.
    const res = await fetch(`${API_URL}/products/${id}`, { next: { revalidate: 30 } });
    if (!res.ok) return null;
    return res.json();
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

  const attributeEntries = Object.entries(product.attributes || {}).filter(
    ([, value]) => value !== "" && value !== null
  );
  const labels = attributeEntries.length > 0 ? await getAttributeLabels(product.category) : {};

  return (
    <main className="max-w-3xl mx-auto px-6 py-10 space-y-4">
      <p className="text-xs text-gray-400">{product.category}</p>
      <h1 className="text-2xl font-bold">{product.name}</h1>
      <p className="text-xl font-semibold">₹{product.price}</p>
      {product.description && <p className="text-gray-600">{product.description}</p>}

      {attributeEntries.length > 0 && (
        <div className="text-sm text-gray-500 space-y-1 bg-gray-50 rounded-lg p-3">
          {attributeEntries.map(([key, value]) => (
            <p key={key}>
              <span className="font-medium text-gray-700">{labels[key] ?? key}:</span>{" "}
              {typeof value === "boolean" ? (value ? "Yes" : "No") : String(value)}
            </p>
          ))}
        </div>
      )}

      <p className="text-sm text-gray-400">
        {product.stock_qty > 0 ? `${product.stock_qty} in stock` : "Out of stock"}
      </p>

      {product.shop && (
        <div className="border-t pt-4 mt-4">
          <p className="text-sm text-gray-500">
            Sold by{" "}
            <Link href={`/store/${product.shop.id}`} className="font-medium text-blue-600 hover:underline">
              {product.shop.name}
            </Link>{" "}
            · ★ {product.shop.rating.toFixed(1)}
          </p>
        </div>
      )}

      <div className="flex items-center gap-3">
        <AddToCartButton productId={product.id} inStock={product.stock_qty > 0} />
        <WishlistButton productId={product.id} />
      </div>
    </main>
  );
}
