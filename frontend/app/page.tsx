import Link from "next/link";

type Category = { name: string; product_count: number };
type Shop = { id: string; name: string; category: string; rating: number };

// A shared helper for the pattern every server-rendered page here uses:
// fetch from the backend, fail soft (empty list) rather than crashing the
// whole page if the API is briefly unreachable.
async function getJSON<T>(path: string, fallback: T): Promise<T> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    // revalidate: 30 -> Next.js's ISR cache. This page doesn't need to be
    // rebuilt on every single request; re-fetching every 30s keeps it fast
    // while still staying reasonably fresh if a shop/category changes.
    const res = await fetch(`${apiUrl}${path}`, { next: { revalidate: 30 } });
    if (!res.ok) throw new Error(`API responded ${res.status}`);
    return res.json();
  } catch {
    return fallback;
  }
}

export default async function Home() {
  // Fetched in parallel, not sequentially — these two calls don't depend
  // on each other, so there's no reason to make the user wait for both
  // round trips back-to-back.
  const [categories, shops] = await Promise.all([
    getJSON<Category[]>("/categories", []),
    getJSON<Shop[]>("/shops", []),
  ]);

  return (
    <main className="max-w-5xl mx-auto px-6 py-10 space-y-12">
      <section className="text-center space-y-3">
        <h1 className="text-4xl font-bold">Your neighborhood, at your fingertips</h1>
        <p className="text-gray-500">Shop from local businesses near you.</p>

        {/* Plain HTML form GET submit -> navigates to /search?q=... server-side.
            No client JS needed for something this simple. */}
        <form action="/search" className="flex justify-center pt-2">
          <input
            type="text"
            name="q"
            placeholder="What are you looking for?"
            className="border rounded-l-md px-4 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button type="submit" className="bg-blue-600 text-white rounded-r-md px-4 py-2 text-sm">
            Search
          </button>
        </form>
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-4">Categories</h2>
        {categories.length === 0 ? (
          <p className="text-sm text-gray-400">
            No categories yet — run the seed script (see backend README).
          </p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {categories.map((c) => (
              <Link
                key={c.name}
                href={`/search?category=${encodeURIComponent(c.name)}`}
                className="border rounded-lg p-4 text-center hover:border-blue-400 transition"
              >
                <p className="font-medium">{c.name}</p>
                <p className="text-xs text-gray-400">{c.product_count} items</p>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="text-lg font-semibold mb-4">Shops near you</h2>
        {shops.length === 0 ? (
          <p className="text-sm text-gray-400">
            No shops yet — run the seed script (see backend README).
          </p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {shops.map((s) => (
              <div key={s.id} className="border rounded-lg p-4">
                <p className="font-medium">{s.name}</p>
                <p className="text-xs text-gray-500">{s.category}</p>
                <p className="text-xs text-yellow-600">★ {s.rating.toFixed(1)}</p>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
