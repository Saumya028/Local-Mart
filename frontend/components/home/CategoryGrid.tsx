import Link from "next/link";
import { categoryIcon, categoryBg } from "@/lib/categoryVisuals";

export type CategoryData = { name: string; product_count: number; shop_count: number };

export function CategoryGrid({ categories }: { categories: CategoryData[] }) {
  return (
    <section id="categories" className="max-w-6xl mx-auto px-6 py-16 scroll-mt-20">
      <div className="flex items-end justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold text-gray-900">Browse Categories</h2>
          <p className="text-sm text-gray-500 mt-1">Find exactly what you need from local shops</p>
        </div>
        <Link href="/search" className="text-sm text-blue-600 hover:underline whitespace-nowrap">
          View all ›
        </Link>
      </div>

      {categories.length === 0 ? (
        <p className="text-sm text-gray-400">No categories yet — run the seed script (see backend README).</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {categories.map((c) => (
            <Link
              key={c.name}
              href={`/search?category=${encodeURIComponent(c.name)}`}
              className="border border-gray-100 rounded-2xl p-5 text-center hover:border-blue-300 hover:shadow-sm transition"
            >
              <div className={`w-12 h-12 mx-auto rounded-xl ${categoryBg(c.name)} flex items-center justify-center text-2xl`}>
                {categoryIcon(c.name)}
              </div>
              <p className="font-semibold text-sm text-gray-900 mt-3">{c.name}</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {c.shop_count > 0 ? `${c.shop_count}+ shops` : `${c.product_count} products`}
              </p>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
