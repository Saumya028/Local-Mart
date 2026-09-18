import { MarketingFooter } from "@/components/home/MarketingFooter";
import { HeroSearch } from "@/components/home/HeroSearch";
import { CategoryGrid, CategoryData } from "@/components/home/CategoryGrid";
import { FeaturedStores, StoreData } from "@/components/home/FeaturedStores";
import { PopularProducts, ProductData } from "@/components/home/PopularProducts";
import { WhyChooseUs } from "@/components/home/WhyChooseUs";
import { Testimonials } from "@/components/home/Testimonials";
import { CTASection } from "@/components/home/CTASection";

type Stats = { total_shops: number; total_customers: number };

// A shared helper for the pattern every server-rendered page here uses:
// fetch from the backend, fail soft (empty/zero fallback) rather than
// crashing the whole page if the API is briefly unreachable.
async function getJSON<T>(path: string, fallback: T): Promise<T> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    // revalidate: 30 -> Next.js's ISR cache. The Landing page doesn't
    // need to be rebuilt on every single request; re-fetching every 30s
    // keeps it fast while still staying reasonably fresh.
    const res = await fetch(`${apiUrl}${path}`, { next: { revalidate: 30 } });
    if (!res.ok) throw new Error(`API responded ${res.status}`);
    return res.json();
  } catch {
    return fallback;
  }
}

export default async function Home() {
  // Fetched in parallel — none of these four calls depend on each
  // other, so there's no reason to make the visitor wait for all four
  // round trips back-to-back.
  const [categories, shops, products, stats] = await Promise.all([
    getJSON<CategoryData[]>("/categories", []),
    getJSON<StoreData[]>("/shops", []),
    getJSON<ProductData[]>("/products?limit=6", []),
    getJSON<Stats>("/stats", { total_shops: 0, total_customers: 0 }),
  ]);

  const featuredShops = shops.slice(0, 4);

  return (
    <div className="flex flex-col min-h-screen">
      <main className="flex-1">
        <section className="bg-gradient-to-br from-blue-50 via-white to-emerald-50 px-6 py-16 sm:py-20 text-center">
          <div className="max-w-3xl mx-auto space-y-6">
            {stats.total_shops > 0 && (
              <span className="inline-flex items-center gap-1.5 text-xs font-medium bg-blue-100 text-blue-700 rounded-full px-3 py-1.5">
                ⚡ {stats.total_shops.toLocaleString("en-IN")}+ local shops on LocalMart
              </span>
            )}
            <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 leading-tight">
              Your neighborhood, <span className="bg-gradient-to-r from-blue-600 to-emerald-500 bg-clip-text text-transparent">at your fingertips</span>
            </h1>
            <p className="text-gray-500 max-w-xl mx-auto">
              Shop from local businesses near you — fresh products, fast delivery, and the joy of supporting your
              community.
            </p>
            <HeroSearch />
          </div>
        </section>

        <CategoryGrid categories={categories} />
        <FeaturedStores shops={featuredShops} />
        <PopularProducts products={products} />
        <WhyChooseUs />
        <Testimonials />
        <CTASection totalCustomers={stats.total_customers} />
      </main>

      <MarketingFooter />
    </div>
  );
}
