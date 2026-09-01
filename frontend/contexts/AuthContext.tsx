"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { supabase } from "@/lib/supabaseClient";
import { apiFetch } from "@/lib/apiClient";

type Profile = { id: string; email: string; full_name: string | null; role: string };

type AuthContextValue = {
  profile: Profile | null;
  loading: boolean;
  loggedIn: boolean;
  refresh: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue>({
  profile: null,
  loading: true,
  loggedIn: false,
  refresh: async () => {},
});

/**
 * Wraps the whole app (see layout.tsx). Fetches /auth/me once, shares the
 * result everywhere via useAuth() — this is what lets the Header decide
 * whether to show "Sell" and the Shop Dashboard decide whether to even
 * attempt loading BEFORE any role-gated request goes out, rather than
 * every consumer independently re-fetching the same profile and finding
 * out about a 403 only after asking.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loggedIn, setLoggedIn] = useState(false);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const { data } = await supabase.auth.getSession();

    if (!data.session) {
      setLoggedIn(false);
      setProfile(null);
      setLoading(false);
      return;
    }

    setLoggedIn(true);
    try {
      const me: Profile = await apiFetch("/auth/me");
      setProfile(me);
    } catch {
      setProfile(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    // Re-check whenever Supabase's own auth state changes (login, logout,
    // token refresh) — this is what keeps the Header/dashboard in sync
    // immediately after signing in or out, without a manual page reload.
    const { data: listener } = supabase.auth.onAuthStateChange(() => {
      refresh();
    });
    return () => listener.subscription.unsubscribe();
  }, [refresh]);

  return (
    <AuthContext.Provider value={{ profile, loading, loggedIn, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
