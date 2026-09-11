"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import AuthStatus from "./AuthStatus";
import { useAuth } from "@/contexts/AuthContext";

const AUTH_ROUTES = ["/login", "/signup", "/forgot-password", "/reset-password"];

/**
 * "use client" here because it renders AuthStatus, which needs the
 * browser's Supabase session. Rendered from the root layout (a Server
 * Component) — a Server Component can render a Client Component anywhere
 * in its JSX, not only via the `children` prop, so this works fine.
 */
export default function Header() {
  const { profile } = useAuth();
  const pathname = usePathname();

  // The auth pages render their own full-bleed two-panel layout with
  // their own "Back to home" link, and "/" renders its own
  // MarketingHeader (components/home/MarketingHeader.tsx) — a
  // discovery-focused header with different nav (Discover/Categories/
  // Stores/For Businesses) than this transactional one
  // (Search/Cart/My Account). Rendering both here AND there would stack
  // two headers on the same page.
  if (pathname === "/" || AUTH_ROUTES.some((route) => pathname?.startsWith(route))) {
    return null;
  }

  // "Sell" only shows for accounts that can actually use it. A plain
  // customer never even sees the link — this is a UX nicety, not the
  // real security boundary (the backend enforces that independently via
  // require_role on every dashboard/shop-creation endpoint), but there's
  // no reason to dangle a link in front of someone that just 403s.
  const canSell = profile?.role === "shop_owner" || profile?.role === "admin";
  const isAdmin = profile?.role === "admin";

  return (
    <header className="border-b border-gray-100">
      <div className="max-w-5xl mx-auto flex items-center justify-between px-6 py-4">
        <Link href="/" className="text-xl font-bold">
          LocalMart
        </Link>
        <nav className="flex items-center gap-6 text-sm">
          <Link href="/search" className="text-gray-600 hover:text-gray-900">
            Search
          </Link>
          {canSell && (
            <Link href="/shop/dashboard" className="text-gray-600 hover:text-gray-900">
              Sell
            </Link>
          )}
          {isAdmin && (
            <Link href="/admin" className="text-gray-600 hover:text-gray-900">
              Admin
            </Link>
          )}
          <Link href="/cart" className="text-gray-600 hover:text-gray-900">
            Cart
          </Link>
          <Link href="/profile" className="text-gray-600 hover:text-gray-900">
            My Account
          </Link>
          <AuthStatus />
        </nav>
      </div>
    </header>
  );
}
