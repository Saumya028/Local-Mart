"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const AUTH_ROUTES = ["/login", "/signup", "/forgot-password", "/reset-password"];

// Same reasoning as Header.tsx: these pages render their own dashboard
// app-shell (Sidebar + Topbar) and shouldn't also get this site footer
// tacked on underneath it.
const APP_SHELL_ROUTES = ["/admin", "/shop/dashboard"];

export default function Footer() {
  const pathname = usePathname();
  // "/" renders its own MarketingFooter (see app/page.tsx).
  if (
    pathname === "/" ||
    AUTH_ROUTES.some((route) => pathname?.startsWith(route)) ||
    APP_SHELL_ROUTES.some((route) => pathname?.startsWith(route))
  ) {
    return null;
  }

  return (
    <footer className="border-t mt-16 py-8 text-sm text-gray-500">
      <div className="max-w-5xl mx-auto px-6 flex flex-wrap items-center justify-between gap-4">
        <p>&copy; {new Date().getFullYear()} LocalMart</p>
        <nav className="flex gap-6">
          <Link href="/privacy" className="hover:text-gray-900">
            Privacy Policy
          </Link>
          <Link href="/terms" className="hover:text-gray-900">
            Terms of Service
          </Link>
        </nav>
      </div>
    </footer>
  );
}
