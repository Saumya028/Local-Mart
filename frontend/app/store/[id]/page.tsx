import Link from "next/link";
import { notFound } from "next/navigation";
import WishlistButton from "@/components/WishlistButton";
import { categoryIcon, categoryBg } from "@/lib/categoryVisuals";

type Shop = { id: string; name: string; category: string; rating: number; is_active: boolean; created_at: string };
type Product = { id: string; name: string; price: string; category: string; images: string[] };

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getShop(id: string): Promise<Shop | null> {
  try {
    // revalidate: 30 -> matches the backend's own Redis cache TTL for
    // GET /shops/{id} (60s) closely enough to stay roughly in sync,
    // same reasoning as the product detail page.
    const res = await fetch(`${API_URL}/shops/${id}`, { next: { revalidate: 30 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function getShopProducts(id: string): Promise<Product[]> {
  try {
    const res = await fetch(`${API_URL}/products?shop_id=${id}&limit=100`, { cache: "no-store" });
    if (!res.ok) return [];
    return res.json();
  } catch {
    return [];
  }
}

export default async function StorePage({ params }: { params: { id: string } }) {
  const shop = await getShop(params.id);
  if (!shop) {
    // GET /shops/{id} 404s for a pending/rejected/deactivated shop too,
    // not only a genuinely nonexistent one — from a visitor's point of
    // view those are indistinguishable anyway ("this isn't a shop you
    // can browse"), so a plain not-found page is the honest response.
    notFound();
  }

  const products = await getShopProducts(shop.id);

  return (
    <main className="max-w-6xl mx-auto px-6 py-10 space-y-8">
      <div className="flex items-center gap-5">
        <div className={`w-20 h-20 rounded-2xl flex items-center justify-center text-4xl shrink-0 ${categoryBg(shop.category)}`}>
          {categoryIcon(shop.category)}
        </div>
        <div>
          <p className="text-sm text-blue-600 font-medium">{shop.category}</p>
          <h1 className="text-2xl font-bold text-gray-900">{shop.name}</h1>
          <p className="text-sm text-amber-500 mt-1">★ {shop.rating.toFixed(1)}</p>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-bold text-gray-900 mb-4">Products</h2>
        {products.length === 0 ? (
          <p className="text-sm text-gray-400">This shop hasn&apos;t listed any products yet.</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {products.map((p) => (
              <div key={p.id} className="border border-gray-100 rounded-2xl overflow-hidden hover:shadow-md transition">
                <div className={`relative h-28 flex items-center justify-center text-3xl overflow-hidden ${categoryBg(p.category)}`}>
                  {p.images?.[0] ? (
                    // eslint-disable-next-line @next/next/no-img-element -- user-uploaded Supabase Storage URL
                    <img src={p.images[0]} alt="" className="absolute inset-0 w-full h-full object-contain p-2 bg-white" />
                  ) : (
                    categoryIcon(p.category)
                  )}
                  <div className="absolute top-2 right-2">
                    <WishlistButton productId={p.id} />
                  </div>
                </div>
                <Link href={`/product/${p.id}`} className="block p-3">
                  <p className="text-sm font-medium text-gray-900 line-clamp-2">{p.name}</p>
                  <p className="text-sm font-semibold text-gray-900 mt-1.5">₹{p.price}</p>
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
