"use client";

import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import AuthStatus from "@/components/AuthStatus";

/**
 * Used ONLY on "/" (see app/page.tsx) — the rest of the app uses the
 * transactional Header (Search/Cart/My Account). This one is the
 * marketing/discovery entry point, so its nav points at discovery
 * surfaces (categories, stores) and a real "For Businesses" path
 * instead.
 */
export function MarketingHeader() {
  const { loggedIn } = useAuth();

  return (
    <header className="border-b border-gray-100">
      <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-2">
          <span className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center">
            <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4">
              <path d="M10 2 2.5 6v8L10 18l7.5-4V6L10 2Z" stroke="white" strokeWidth="1.4" fill="white" fillOpacity={0.2} />
            </svg>
          </span>
          <span className="text-lg font-bold text-gray-900">LocalMart</span>
        </Link>

        <nav className="hidden md:flex items-center gap-8 text-sm text-gray-600">
          <Link href="/search" className="hover:text-gray-900">
            Discover
          </Link>
          <Link href="/#categories" className="hover:text-gray-900">
            Categories
          </Link>
          <Link href="/stores" className="hover:text-gray-900">
            Stores
          </Link>
          <Link href="/shop/dashboard" className="hover:text-gray-900">
            For Businesses
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          {loggedIn ? (
            <AuthStatus />
          ) : (
            <>
              <Link href="/login" className="text-sm text-gray-600 hover:text-gray-900">
                Sign In
              </Link>
              <Link
                href="/signup"
                className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg px-4 py-2 transition"
              >
                Get Started
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
