import Link from "next/link";
import { categoryIcon, categoryBg } from "@/lib/categoryVisuals";

type Product = {
  id: string;
  name: string;
  price: string;
  category: string;
  images: string[];
};

async function searchProducts(q?: string, category?: string): Promise<Product[]> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (category) params.set("category", category);

  try {
    // no-store: search results should always reflect the current query,
    // never a stale cached page — unlike the Landing page's categories.
    const res = await fetch(`${apiUrl}/products?${params.toString()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`API responded ${res.status}`);
    return res.json();
  } catch {
    return [];
  }
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: { q?: string; category?: string };
}) {
  const products = await searchProducts(searchParams.q, searchParams.category);

  const heading = searchParams.category
    ? `Category: ${searchParams.category}`
    : searchParams.q
    ? `Results for "${searchParams.q}"`
    : "All products";

  return (
    <main className="max-w-5xl mx-auto px-6 py-10 space-y-6">
      <h1 className="text-2xl font-bold">{heading}</h1>

      {products.length === 0 ? (
        <p className="text-sm text-gray-400">No products found.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {products.map((p) => (
            <Link
              key={p.id}
              href={`/product/${p.id}`}
              className="border rounded-lg overflow-hidden hover:border-blue-400 transition"
            >
              <div className={`relative h-24 flex items-center justify-center text-2xl overflow-hidden ${categoryBg(p.category)}`}>
                {p.images?.[0] ? (
                  // eslint-disable-next-line @next/next/no-img-element -- user-uploaded Supabase Storage URL
                  <img src={p.images[0]} alt="" className="absolute inset-0 w-full h-full object-contain p-2 bg-white" />
                ) : (
                  categoryIcon(p.category)
                )}
              </div>
              <div className="p-3">
                <p className="font-medium text-sm">{p.name}</p>
                <p className="text-xs text-gray-500">{p.category}</p>
                <p className="text-sm font-semibold mt-1">₹{p.price}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
