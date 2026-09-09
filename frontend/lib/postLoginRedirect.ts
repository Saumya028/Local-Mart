const KEY = "localmart:post_login_redirect";

/**
 * Backs the Login page's "Or sign in as Shop Owner / Admin" buttons.
 * These do NOT grant any role — they just record where to land after a
 * REAL sign-in succeeds. If the account that actually logs in isn't a
 * shop_owner/admin, it lands on that page anyway and sees the same
 * polite "not available for your account" message /shop/dashboard and
 * /admin already show everyone else — the buttons are a navigation
 * shortcut, never a permission grant.
 */
export function setPostLoginRedirect(path: string) {
  if (typeof window !== "undefined") sessionStorage.setItem(KEY, path);
}

export function consumePostLoginRedirect(fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const stored = sessionStorage.getItem(KEY);
  if (stored) {
    sessionStorage.removeItem(KEY);
    return stored;
  }
  return fallback;
}
