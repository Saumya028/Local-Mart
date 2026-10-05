"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { setPostLoginRedirect } from "@/lib/postLoginRedirect";

// Friendly "you need to be signed in for this" panel, used instead of
// showing a raw 401 error on pages that only make sense for a logged-in
// customer (cart, checkout, orders…). Remembers where the person was
// headed so they land back there right after signing in.
export default function SignInPrompt({
  title,
  description,
  returnTo,
  icon,
}: {
  title: string;
  description: string;
  returnTo: string;
  icon: ReactNode;
}) {
  return (
    <main className="max-w-lg mx-auto px-4 sm:px-6 py-12 sm:py-20">
      <div className="bg-white border border-gray-100 rounded-3xl shadow-sm px-6 sm:px-10 py-10 text-center">
        <div className="mx-auto w-16 h-16 rounded-2xl bg-blue-50 text-blue-600 flex items-center justify-center">
          {icon}
        </div>
        <h1 className="mt-6 text-2xl font-bold text-gray-900">{title}</h1>
        <p className="mt-2 text-sm text-gray-500 leading-relaxed">{description}</p>

        <div className="mt-8 flex flex-col gap-3">
          <Link
            href="/login"
            onClick={() => setPostLoginRedirect(returnTo)}
            className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-xl py-3 text-sm font-semibold transition-colors"
          >
            Log in
          </Link>
          <Link
            href="/signup"
            onClick={() => setPostLoginRedirect(returnTo)}
            className="w-full border border-gray-200 hover:bg-gray-50 text-gray-700 rounded-xl py-3 text-sm font-semibold transition-colors"
          >
            Create an account
          </Link>
        </div>

        <Link href="/stores" className="mt-6 inline-block text-sm text-gray-500 hover:text-gray-700 hover:underline">
          ← Keep browsing stores
        </Link>
      </div>
    </main>
  );
}
