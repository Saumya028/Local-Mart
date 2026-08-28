"use client";

import Link from "next/link";
import AuthStatus from "./AuthStatus";

/**
 * "use client" here because it renders AuthStatus, which needs the
 * browser's Supabase session. Rendered from the root layout (a Server
 * Component) — a Server Component can render a Client Component anywhere
 * in its JSX, not only via the `children` prop, so this works fine.
 */
export default function Header() {
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
          <Link href="/cart" className="text-gray-600 hover:text-gray-900">
            Cart
          </Link>
          <AuthStatus />
        </nav>
      </div>
    </header>
  );
}
