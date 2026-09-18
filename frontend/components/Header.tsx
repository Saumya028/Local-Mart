"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import AuthStatus from "./AuthStatus";
import { useAuth } from "@/contexts/AuthContext";

const AUTH_ROUTES = ["/login", "/signup", "/forgot-password", "/reset-password"];

// Routes that render their own complete app-shell (a Sidebar + Topbar of
// their own — see components/admin and components/shop-dashboard). This
// site-wide Header is for the customer/marketing-facing pages only;
// stacking it above a dashboard's own chrome would just be a second,
// redundant nav bar on top of the real one.
const APP_SHELL_ROUTES = ["/admin", "/shop/dashboard"];

function isExcludedRoute(pathname: string | null) {
  if (!pathname) return false;
  return (
    AUTH_ROUTES.some((route) => pathname.startsWith(route)) ||
    APP_SHELL_ROUTES.some((route) => pathname.startsWith(route))
  );
}

/**
 * The single header used across the entire customer-facing site — home,
 * search, stores, product/store pages, cart, checkout, account, etc. —
 * so branding and navigation are identical no matter which page someone
 * lands on. The only pages that opt out are the auth pages (which render
 * their own full-bleed two-panel layout, see components/auth/AuthLayout)
 * and the admin/shop-dashboard pages (which render their own sidebar
 * app-shell), since either of those getting this header on top as well
 * would just stack two navs.
 *
 * "use client" here because it renders AuthStatus, which needs the
 * browser's Supabase session. Rendered from the root layout (a Server
 * Component) — a Server Component can render a Client Component anywhere
 * in its JSX, not only via the `children` prop, so this works fine.
 */
export default function Header() {
  const { profile } = useAuth();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (isExcludedRoute(pathname)) {
    return null;
  }

  // "Sell" only shows for accounts that can actually use it. A plain
  // customer never even sees the link — this is a UX nicety, not the
  // real security boundary (the backend enforces that independently via
  // require_role on every dashboard/shop-creation endpoint), but there's
  // no reason to dangle a link in front of someone that just 403s.
  const canSell = profile?.role === "shop_owner" || profile?.role === "admin";
  const isAdmin = profile?.role === "admin";

  const navLinks = [
    { href: "/search", label: "Search" },
    { href: "/stores", label: "Stores" },
    ...(canSell ? [{ href: "/shop/dashboard", label: "Sell" }] : []),
    ...(isAdmin ? [{ href: "/admin", label: "Admin" }] : []),
    { href: "/cart", label: "Cart" },
    { href: "/profile", label: "My Account" },
  ];

  const isActive = (href: string) => pathname === href || (href !== "/" && pathname?.startsWith(href));

  return (
    <header className="border-b border-gray-100 relative z-20">
      <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4 gap-4">
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <span className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center">
            <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
              <path d="M10 2 2.5 6v8L10 18l7.5-4V6L10 2Z" stroke="white" strokeWidth="1.4" fill="white" fillOpacity={0.2} />
            </svg>
          </span>
          <span className="text-lg font-bold text-gray-900">LocalMart</span>
        </Link>

        <nav className="hidden md:flex items-center gap-6 text-sm">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={
                isActive(link.href)
                  ? "text-gray-900 font-medium"
                  : "text-gray-600 hover:text-gray-900"
              }
            >
              {link.label}
            </Link>
          ))}
          <AuthStatus />
        </nav>

        <button
          type="button"
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
          aria-expanded={mobileOpen}
          onClick={() => setMobileOpen((open) => !open)}
          className="md:hidden text-gray-600 hover:text-gray-900 p-1"
        >
          <svg viewBox="0 0 20 20" fill="none" className="w-6 h-6">
            {mobileOpen ? (
              <path d="M5 5l10 10M15 5 5 15" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            ) : (
              <path d="M3 5h14M3 10h14M3 15h14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            )}
          </svg>
        </button>
      </div>

      {mobileOpen && (
        <nav className="md:hidden border-t border-gray-100 px-6 py-4 flex flex-col gap-4 text-sm bg-white">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMobileOpen(false)}
              className={isActive(link.href) ? "text-gray-900 font-medium" : "text-gray-600 hover:text-gray-900"}
            >
              {link.label}
            </Link>
          ))}
          <div className="pt-2 border-t border-gray-100">
            <AuthStatus />
          </div>
        </nav>
      )}
    </header>
  );
}
