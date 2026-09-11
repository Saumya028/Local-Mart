const TESTIMONIALS = [
  {
    quote: "Getting fresh groceries from my nearby store within minutes has completely changed how I shop.",
    name: "Ananya Rao",
    role: "Homemaker",
    initials: "AR",
  },
  {
    quote: "Supporting local businesses while getting the convenience of online shopping — exactly what our neighborhood needed.",
    name: "Rohan Desai",
    role: "Software Engineer",
    initials: "RD",
  },
  {
    quote: "Product discovery is great — I found local shops just a few minutes from home that I never knew existed.",
    name: "Meera Iyer",
    role: "Freelance Designer",
    initials: "MI",
  },
];

export function Testimonials() {
  return (
    <section className="max-w-6xl mx-auto px-6 py-16">
      <div className="text-center mb-10">
        <h2 className="text-2xl font-bold text-gray-900">Loved by our early customers</h2>
        <p className="text-sm text-gray-500 mt-1">A few notes from people shopping LocalMart</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        {TESTIMONIALS.map((t) => (
          <div key={t.name} className="border border-gray-100 rounded-2xl p-6">
            <p className="text-amber-400 text-sm mb-3">★★★★★</p>
            <p className="text-sm text-gray-600">&ldquo;{t.quote}&rdquo;</p>
            <div className="flex items-center gap-2.5 mt-4">
              <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 text-xs font-semibold flex items-center justify-center">
                {t.initials}
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">{t.name}</p>
                <p className="text-xs text-gray-400">{t.role}</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
