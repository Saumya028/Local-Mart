import Link from "next/link";
import { categoryIcon, categoryBg } from "@/lib/categoryVisuals";
import { RatingBadge } from "@/components/reviews/StarRating";

export type StoreData = { id: string; name: string; category: string; rating: number; rating_count?: number; created_at: string };

const NEW_WITHIN_DAYS = 14;

function badgeFor(shop: StoreData, topRatedId: string | undefined): { label: string; className: string } | null {
  // Only a shop with real reviews can be "Top Rated".
  if (shop.id === topRatedId && (shop.rating_count ?? 0) > 0) return { label: "Top Rated", className: "bg-blue-600 text-white" };
  const ageDays = (Date.now() - new Date(shop.created_at).getTime()) / 86400000;
  if (ageDays <= NEW_WITHIN_DAYS) return { label: "New", className: "bg-emerald-500 text-white" };
  return null;
}

export function FeaturedStores({ shops }: { shops: StoreData[] }) {
  const topRatedId = shops[0]?.id;

  return (
    <section className="max-w-6xl mx-auto px-6 py-16">
      <div className="flex items-end justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Featured Stores</h2>
          <p className="text-sm text-gray-500 mt-1">Handpicked shops with stellar reviews</p>
        </div>
        <Link href="/stores" className="text-sm border border-gray-200 rounded-lg px-4 py-2 hover:bg-gray-50 whitespace-nowrap">
          See all stores
        </Link>
      </div>

      {shops.length === 0 ? (
        <p className="text-sm text-gray-400">No shops yet — run the seed script (see backend README).</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {shops.map((shop) => {
            const badge = badgeFor(shop, topRatedId);
            return (
              <Link
                key={shop.id}
                href={`/store/${shop.id}`}
                className="border border-gray-100 rounded-2xl overflow-hidden hover:shadow-md transition block"
              >
                <div className={`relative h-32 flex items-center justify-center text-4xl ${categoryBg(shop.category)}`}>
                  {categoryIcon(shop.category)}
                  {badge && (
                    <span className={`absolute top-2 left-2 text-xs font-medium rounded-full px-2 py-1 ${badge.className}`}>
                      {badge.label}
                    </span>
                  )}
                </div>
                <div className="p-4">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs text-blue-600 font-medium">{shop.category}</p>
                  </div>
                  <p className="font-semibold text-gray-900 text-sm mt-0.5">{shop.name}</p>
                  <p className="mt-1.5"><RatingBadge average={shop.rating} count={shop.rating_count ?? 0} /></p>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}
