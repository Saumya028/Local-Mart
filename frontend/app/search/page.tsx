import { PriceTag } from "@/components/product/PriceTag";
import Link from "next/link";
import { SetLocationPrompt } from "@/components/location/SetLocationPrompt";
import { getServerLocation } from "@/lib/serverLocation";
import { BannerSlot } from "@/components/banners/BannerSlot";
import { categoryIcon, categoryBg } from "@/lib/categoryVisuals";
import { RatingBadge } from "@/components/reviews/StarRating";

type Product = {
  id: string;
  name: string;
  price: string;
  mrp?: string | null;
  discount_percent?: number | null;
  unit_label?: string | null;
  stock_qty?: number;
  category: string;
  images: string[];
  rating_avg?: number;
  rating_count?: number;
  shop_name?: string | null;
  distance_km?: number | null;
};

const PAGE_SIZE = 24;

async function searchProducts(
  q: string | undefined,
  category: string | undefined,
  lat: number,
  lng: number,
  page = 1,
): Promise<{ products: Product[]; hasMore: boolean }> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const params = new URLSearchParams();
  // Ask for one extra row: if it comes back, there is a next page.
  params.set("limit", String(PAGE_SIZE + 1));
  params.set("offset", String((page - 1) * PAGE_SIZE));
  if (q) params.set("q", q);
  if (category) params.set("category", category);
  params.set("lat", String(lat));
  params.set("lng", String(lng));

  try {
    // no-store: search results should always reflect the current query,
    // never a stale cached page — unlike the Landing page's categories.
    const res = await fetch(`${apiUrl}/products?${params.toString()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`API responded ${res.status}`);
    const rows: Product[] = await res.json();
    return { products: rows.slice(0, PAGE_SIZE), hasMore: rows.length > PAGE_SIZE };
  } catch {
    return { products: [], hasMore: false };
  }
}

export default async function SearchPage({
  searchParams: searchParamsPromise,
}: {
  // In Next.js 15+ searchParams is a Promise and must be awaited.
  searchParams: Promise<{ q?: string; category?: string; page?: string }>;
}) {
  const searchParams = await searchParamsPromise;
  const page = Math.min(Math.max(parseInt(searchParams.page ?? "1", 10) || 1, 1), 400);
  const loc = await getServerLocation();
  if (!loc) {
    return (
      <main className="max-w-5xl mx-auto px-6 py-16">
        <SetLocationPrompt />
      </main>
    );
  }
  const { products, hasMore } = await searchProducts(searchParams.q, searchParams.category, loc.lat, loc.lng, page);
  const pageHref = (n: number) => {
    const qs = new URLSearchParams();
    if (searchParams.q) qs.set("q", searchParams.q);
    if (searchParams.category) qs.set("category", searchParams.category);
    if (n > 1) qs.set("page", String(n));
    const str = qs.toString();
    return str ? `/search?${str}` : "/search";
  };

  const heading = searchParams.category
    ? `Category: ${searchParams.category}`
    : searchParams.q
    ? `Results for "${searchParams.q}"`
    : "All products";

  return (
    <main className="max-w-5xl mx-auto px-6 py-10 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold">{heading}</h1>
      </div>

      <BannerSlot slot="search_top" promptForLocation className="!px-0" />

      <form action="/search" className="flex gap-2 max-w-xl">
        <input
          name="q"
          defaultValue={searchParams.q}
          placeholder="Search products — e.g. ball pen, bread, paracetamol…"
          className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        {searchParams.category && <input type="hidden" name="category" value={searchParams.category} />}
        <button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition">
          Search
        </button>
      </form>

      {searchParams.category && (
        <Link href="/search" className="text-sm text-blue-600 hover:underline inline-block">
          ← Clear category filter
        </Link>
      )}

      {products.length === 0 ? (
        <p className="text-sm text-gray-400">No matching products from shops that deliver to you.</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {products.map((p) => (
            <Link
              key={p.id}
              prefetch={false} href={`/product/${p.id}`}
              className="border rounded-lg overflow-hidden hover:border-blue-400 transition"
            >
              <div className={`relative h-24 flex items-center justify-center text-2xl overflow-hidden ${categoryBg(p.category)}`}>
                {p.images?.[0] ? (
                  // eslint-disable-next-line @next/next/no-img-element -- user-uploaded Supabase Storage URL
                  <img loading="lazy" decoding="async" src={p.images[0]} alt="" className="absolute inset-0 w-full h-full object-contain p-2 bg-white" />
                ) : (
                  categoryIcon(p.category)
                )}
              </div>
              <div className="p-3">
                <p className="font-medium text-sm mt-1">{p.name}</p>
                {p.shop_name && (
                  <p className="text-xs text-gray-400">
                    {p.shop_name}
                    {p.distance_km != null && ` · ${p.distance_km} km`}
                  </p>
                )}
                <p className="text-xs text-gray-500">{p.category}</p>
                <PriceTag p={p} className="mt-1" />
                {(p.rating_count ?? 0) > 0 && (
                  <p className="mt-0.5"><RatingBadge average={p.rating_avg ?? 0} count={p.rating_count ?? 0} /></p>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}

      {(page > 1 || hasMore) && (
        <nav className="flex items-center justify-between pt-2 text-sm" aria-label="Pagination">
          {page > 1 ? (
            <Link href={pageHref(page - 1)} className="text-blue-600 hover:underline">← Previous</Link>
          ) : (
            <span />
          )}
          <span className="text-gray-400">Page {page}</span>
          {hasMore ? (
            <Link href={pageHref(page + 1)} className="text-blue-600 hover:underline">Next →</Link>
          ) : (
            <span />
          )}
        </nav>
      )}
    </main>
  );
}
