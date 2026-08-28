type ShopInfo = { id: string; name: string; category: string; rating: number };

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

import AddToCartButton from "@/components/AddToCartButton";

async function getProduct(id: string): Promise<ProductDetail | null> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    // revalidate: 30 -> product pages are read far more than written, and
    // this matches the backend's own Redis cache TTL for the same
    // endpoint (60s) closely enough that the two layers stay in sync.
    const res = await fetch(`${apiUrl}/products/${id}`, { next: { revalidate: 30 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
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

  const attributeEntries = Object.entries(product.attributes || {});

  return (
    <main className="max-w-3xl mx-auto px-6 py-10 space-y-4">
      <p className="text-xs text-gray-400">{product.category}</p>
      <h1 className="text-2xl font-bold">{product.name}</h1>
      <p className="text-xl font-semibold">₹{product.price}</p>
      {product.description && <p className="text-gray-600">{product.description}</p>}

      {attributeEntries.length > 0 && (
        <div className="text-sm text-gray-500 space-y-1">
          {attributeEntries.map(([key, value]) => (
            <p key={key}>
              <span className="font-medium">{key}:</span> {String(value)}
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
            Sold by <span className="font-medium">{product.shop.name}</span> · ★{" "}
            {product.shop.rating.toFixed(1)}
          </p>
        </div>
      )}

      <AddToCartButton productId={product.id} inStock={product.stock_qty > 0} />
    </main>
  );
}
