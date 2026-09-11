import Link from "next/link";

export function CTASection({ totalCustomers }: { totalCustomers: number }) {
  return (
    <section className="max-w-6xl mx-auto px-6 py-16">
      <div className="bg-gradient-to-br from-emerald-50 to-blue-50 rounded-3xl px-8 py-14 text-center space-y-4">
        <span className="inline-block text-xs font-medium bg-emerald-100 text-emerald-700 rounded-full px-3 py-1">
          Free delivery on first order
        </span>
        <h2 className="text-2xl sm:text-3xl font-bold text-gray-900">Start shopping locally today</h2>
        <p className="text-sm text-gray-500 max-w-md mx-auto">
          {totalCustomers > 0
            ? `Join ${totalCustomers.toLocaleString("en-IN")}+ customers who shop from neighborhood businesses every day.`
            : "Shop from neighborhood businesses every day."}
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <Link
            href="/search"
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg px-6 py-3 transition w-full sm:w-auto"
          >
            Explore Now
          </Link>
          <Link
            href="/shop/dashboard"
            className="bg-white border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm font-medium rounded-lg px-6 py-3 transition w-full sm:w-auto"
          >
            List Your Shop
          </Link>
        </div>
      </div>
    </section>
  );
}
