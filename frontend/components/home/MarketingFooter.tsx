import Link from "next/link";

const API_DOCS_URL = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/docs`;

const COLUMNS: { title: string; links: { label: string; href: string; external?: boolean }[] }[] = [
  {
    title: "Company",
    links: [
      { label: "About Us", href: "/about" },
      { label: "Careers", href: "/careers" },
    ],
  },
  {
    title: "Platform",
    links: [
      { label: "For Businesses", href: "/shop/dashboard" },
      { label: "Pricing", href: "/pricing" },
      { label: "API", href: API_DOCS_URL, external: true },
      { label: "Status", href: "/status" },
    ],
  },
  {
    title: "Support",
    links: [
      { label: "Help Center", href: "/help" },
      { label: "Contact Us", href: "/contact" },
      { label: "Terms", href: "/terms" },
      { label: "Privacy", href: "/privacy" },
    ],
  },
];

export function MarketingFooter() {
  return (
    <footer className="bg-gray-950 text-gray-300">
      <div className="max-w-6xl mx-auto px-6 py-14 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-10">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <span className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center">
              <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
                <path d="M10 2 2.5 6v8L10 18l7.5-4V6L10 2Z" stroke="white" strokeWidth="1.4" fill="white" fillOpacity={0.2} />
              </svg>
            </span>
            <span className="text-white font-bold">LocalMart</span>
          </div>
          <p className="text-sm text-gray-400">
            Connecting local shops with nearby customers. Building stronger communities, one purchase at a time.
          </p>
        </div>

        {COLUMNS.map((col) => (
          <div key={col.title}>
            <p className="text-white font-semibold text-sm mb-3">{col.title}</p>
            <ul className="space-y-2 text-sm">
              {col.links.map((link) =>
                link.external ? (
                  <li key={link.label}>
                    <a href={link.href} target="_blank" rel="noreferrer" className="hover:text-white">
                      {link.label}
                    </a>
                  </li>
                ) : (
                  <li key={link.label}>
                    <Link href={link.href} className="hover:text-white">
                      {link.label}
                    </Link>
                  </li>
                )
              )}
            </ul>
          </div>
        ))}
      </div>

      <div className="border-t border-gray-800">
        <div className="max-w-6xl mx-auto px-6 py-5 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-gray-500">
          <p>&copy; {new Date().getFullYear()} LocalMart Technologies Pvt. Ltd. All rights reserved.</p>
          <div className="flex items-center gap-4">
            <a href="tel:+918012345678" className="hover:text-gray-300">
              +91 80 1234 5678
            </a>
            <a href="mailto:hello@localmart.in" className="hover:text-gray-300">
              hello@localmart.in
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}
