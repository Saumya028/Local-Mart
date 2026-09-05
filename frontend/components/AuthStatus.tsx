"use client";

import Link from "next/link";
import { supabase } from "@/lib/supabaseClient";
import { useAuth } from "@/contexts/AuthContext";

/**
 * Now a thin consumer of AuthContext rather than fetching /auth/me
 * itself — the Header (which renders this) and the Shop Dashboard page
 * both need the same profile/role, so it's fetched once, centrally, and
 * shared, instead of every component re-fetching it independently.
 */
export default function AuthStatus() {
  const { profile, loading, loggedIn } = useAuth();

  async function handleLogout() {
    await supabase.auth.signOut();
    // A full page reload (not router.push) is deliberate here: it
    // guarantees AuthContext and any other component's in-memory state
    // resets completely on logout, rather than relying on every
    // consumer to correctly react to a soft client-side navigation.
    // Logout is infrequent enough that the extra reload cost is a
    // non-issue.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/";
  }

  if (loading) {
    return <p className="text-sm text-gray-400">Checking session…</p>;
  }

  if (!loggedIn) {
    return (
      <Link href="/login" className="text-sm text-blue-600 underline">
        Log in / Sign up
      </Link>
    );
  }

  return (
    <div className="text-sm space-y-1 text-center">
      <p>
        Logged in as <span className="font-medium">{profile?.email}</span>
      </p>
      <p className="text-gray-500">Role: {profile?.role ?? "unknown"}</p>
      <button onClick={handleLogout} className="text-xs text-red-500 underline">
        Log out
      </button>
    </div>
  );
}
