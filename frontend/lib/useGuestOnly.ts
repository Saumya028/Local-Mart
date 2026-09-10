"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

/**
 * For pages that only make sense to a logged-OUT visitor: /login,
 * /signup, /forgot-password. Deliberately NOT used on /reset-password —
 * that page is reached via a recovery-link click, which itself
 * establishes a (recovery) session. Guarding it the same way would bounce
 * a user away the instant that session appears, before they ever get to
 * set a new password — the opposite of what the page is for.
 *
 * Returns `true` while the caller should show a plain loading state
 * instead of the real form: either auth hasn't resolved yet, or it HAS
 * resolved and found a logged-in session, in which case the redirect
 * below is already underway. Rendering the form during that window
 * would flash it for a moment before the redirect kicks in.
 */
export function useGuestOnly(redirectTo: string = "/") {
  const { loggedIn, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && loggedIn) {
      router.replace(redirectTo);
    }
  }, [loading, loggedIn, redirectTo, router]);

  return { checking: loading || loggedIn };
}
