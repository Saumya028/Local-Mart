import Link from "next/link";
import { categoryIcon, categoryBg } from "@/lib/categoryVisuals";

type Shop = { id: string; name: string; category: string; rating: number; created_at: string };

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function searchShops(q?: string, category?: string): Promise<Shop[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (category) params.set("category", category);
  params.set("limit", "100");

  try {
    // no-store: same reasoning as /search — results should always
    // reflect the current query, never a stale cached page.
    const res = await fetch(`${API_URL}/shops?${params.toString()}`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function StoresPage({
  searchParams,
}: {
  searchParams: { q?: string; category?: string };
}) {
  const shops = await searchShops(searchParams.q, searchParams.category);

  const heading = searchParams.category
    ? `${searchParams.category} stores`
    : searchParams.q
    ? `Stores matching "${searchParams.q}"`
    : "All stores";

  return (
    <main className="max-w-6xl mx-auto px-6 py-10 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{heading}</h1>
        <p className="text-sm text-gray-500 mt-1">{shops.length} shop{shops.length === 1 ? "" : "s"}</p>
      </div>

      <form className="flex gap-2 max-w-md">
        <input
          name="q"
          defaultValue={searchParams.q}
          placeholder="Search stores by name…"
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {searchParams.category && <input type="hidden" name="category" value={searchParams.category} />}
        <button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition">
          Search
        </button>
      </form>

      {searchParams.category && (
        <Link href="/stores" className="text-sm text-blue-600 hover:underline inline-block">
          ← Clear category filter
        </Link>
      )}

      {shops.length === 0 ? (
        <p className="text-sm text-gray-400">No stores found.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {shops.map((shop) => (
            <Link
              key={shop.id}
              href={`/store/${shop.id}`}
              className="border border-gray-100 rounded-2xl overflow-hidden hover:shadow-md transition block"
            >
              <div className={`h-28 flex items-center justify-center text-3xl ${categoryBg(shop.category)}`}>
                {categoryIcon(shop.category)}
              </div>
              <div className="p-4">
                <p className="text-xs text-blue-600 font-medium">{shop.category}</p>
                <p className="font-semibold text-gray-900 text-sm mt-0.5">{shop.name}</p>
                <p className="text-xs text-amber-500 mt-1.5">★ {shop.rating.toFixed(1)}</p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
