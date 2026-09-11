import Link from "next/link";
import WishlistButton from "@/components/WishlistButton";
import { categoryIcon, categoryBg } from "@/lib/categoryVisuals";

export type ProductData = { id: string; name: string; price: string; category: string };

export function PopularProducts({ products }: { products: ProductData[] }) {
  return (
    <section className="max-w-6xl mx-auto px-6 py-16">
      <div className="flex items-end justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Popular Right Now</h2>
          <p className="text-sm text-gray-500 mt-1">Products from local stores near you</p>
        </div>
        <Link href="/search" className="text-sm text-blue-600 hover:underline whitespace-nowrap">
          Browse all ›
        </Link>
      </div>

      {products.length === 0 ? (
        <p className="text-sm text-gray-400">No products yet — run the seed script (see backend README).</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          {products.map((p) => (
            <div key={p.id} className="border border-gray-100 rounded-2xl overflow-hidden hover:shadow-md transition">
              <div className={`relative h-28 flex items-center justify-center text-3xl ${categoryBg(p.category)}`}>
                {categoryIcon(p.category)}
                <div className="absolute top-2 right-2">
                  <WishlistButton productId={p.id} />
                </div>
              </div>
              <Link href={`/product/${p.id}`} className="block p-3">
                <p className="text-xs text-gray-400">{p.category}</p>
                <p className="text-sm font-medium text-gray-900 mt-0.5 line-clamp-2">{p.name}</p>
                <p className="text-sm font-semibold text-gray-900 mt-1.5">₹{p.price}</p>
              </Link>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
