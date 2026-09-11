const ITEMS = [
  {
    icon: "⚡",
    title: "Lightning Fast",
    desc: "Get products from local shops in as little as 15 minutes.",
  },
  {
    icon: "🛡️",
    title: "Verified Stores",
    desc: "Every shop goes through document verification before it goes live.",
  },
  {
    icon: "❤️",
    title: "Support Local",
    desc: "Every purchase directly supports a business in your neighborhood.",
  },
  {
    icon: "📦",
    title: "Easy Returns",
    desc: "Straightforward returns handled directly with the shop.",
  },
];

export function WhyChooseUs() {
  return (
    <section className="bg-gradient-to-br from-blue-600 to-blue-500 text-white">
      <div className="max-w-6xl mx-auto px-6 py-16 text-center space-y-10">
        <div>
          <h2 className="text-2xl sm:text-3xl font-bold">Why choose LocalMart?</h2>
          <p className="text-blue-100 mt-2 max-w-xl mx-auto">
            We&apos;re building a better way to shop — one that benefits you and your community.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 text-left">
          {ITEMS.map((item) => (
            <div key={item.title} className="bg-white/10 rounded-2xl p-5">
              <div className="w-10 h-10 rounded-lg bg-white/15 flex items-center justify-center text-xl">{item.icon}</div>
              <p className="font-semibold mt-3">{item.title}</p>
              <p className="text-sm text-blue-100 mt-1">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
