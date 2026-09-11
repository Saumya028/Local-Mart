"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

const QUICK_SEARCHES = ["Organic groceries", "Fresh bread", "Medicines", "Electronics"];

export function HeroSearch() {
  const router = useRouter();
  const { loggedIn } = useAuth();
  const [q, setQ] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    router.push(q.trim() ? `/search?q=${encodeURIComponent(q.trim())}` : "/search");
  }

  return (
    <div className="space-y-2">
      <form
        onSubmit={handleSubmit}
        className="flex flex-col sm:flex-row items-stretch sm:items-center bg-white border border-gray-200 rounded-2xl sm:rounded-full shadow-sm overflow-hidden max-w-2xl mx-auto"
      >
        <Link
          href={loggedIn ? "/profile?tab=addresses" : "/login"}
          title={loggedIn ? "Manage your delivery addresses" : "Log in to set a delivery address"}
          className="flex items-center gap-1.5 px-4 py-3 text-sm text-gray-600 border-b sm:border-b-0 sm:border-r border-gray-100 hover:bg-gray-50 whitespace-nowrap"
        >
          <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4 text-blue-600 shrink-0">
            <path
              d="M10 18s6-5.5 6-10a6 6 0 1 0-12 0c0 4.5 6 10 6 10Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <circle cx="10" cy="8" r="2" stroke="currentColor" strokeWidth="1.5" />
          </svg>
          {loggedIn ? "Set location" : "Sign in for delivery"}
        </Link>
        <div className="flex-1 flex items-center gap-2 px-4 py-3">
          <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4 text-gray-400 shrink-0">
            <circle cx="8.5" cy="8.5" r="5.5" stroke="currentColor" strokeWidth="1.5" />
            <path d="M16 16l-3.5-3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="What are you looking for?"
            className="flex-1 text-sm focus:outline-none"
          />
        </div>
        <button
          type="submit"
          className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-6 py-3 sm:rounded-full transition"
        >
          Search
        </button>
      </form>

      <p className="text-xs text-gray-400 text-center">
        Popular:{" "}
        {QUICK_SEARCHES.map((term, i) => (
          <span key={term}>
            <Link href={`/search?q=${encodeURIComponent(term)}`} className="hover:text-gray-600 hover:underline">
              {term}
            </Link>
            {i < QUICK_SEARCHES.length - 1 && " · "}
          </span>
        ))}
      </p>
    </div>
  );
}
