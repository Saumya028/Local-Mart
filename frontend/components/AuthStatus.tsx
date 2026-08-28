"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabaseClient";
import { apiFetch } from "@/lib/apiClient";

type Profile = {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
};

/**
 * This has to be a Client Component (unlike the health check on the home
 * page) because it needs the Supabase session, which lives in the
 * browser. It's the piece that proves the FULL auth chain works:
 * Supabase login -> JWT stored in browser -> sent to FastAPI ->
 * verified -> profile row read/created in Postgres -> returned here.
 */
export default function AuthStatus() {
  const [loading, setLoading] = useState(true);
  const [loggedIn, setLoggedIn] = useState(false);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function load() {
      const { data } = await supabase.auth.getSession();
      if (!mounted) return;

      if (!data.session) {
        setLoggedIn(false);
        setLoading(false);
        return;
      }

      setLoggedIn(true);
      try {
        const me = await apiFetch("/auth/me");
        if (mounted) setProfile(me);
      } catch (err) {
        if (mounted) setFetchError((err as Error).message);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
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

  if (fetchError) {
    return (
      <p className="text-sm text-red-500 max-w-sm text-center">
        Logged in, but the API call failed: {fetchError}
      </p>
    );
  }

  return (
    <div className="text-sm space-y-1 text-center">
      <p>
        Logged in as <span className="font-medium">{profile?.email}</span>
      </p>
      <p className="text-gray-500">Role: {profile?.role}</p>
      <button onClick={handleLogout} className="text-xs text-red-500 underline">
        Log out
      </button>
    </div>
  );
}
