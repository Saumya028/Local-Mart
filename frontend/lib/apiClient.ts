import { supabase } from "./supabaseClient";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Wraps fetch() so every call to our FastAPI backend automatically carries
 * the current Supabase session's access token, if there is one. Every
 * other part of the app should call the backend through this function
 * rather than raw fetch(), so we never forget the auth header in one spot.
 */
export async function apiFetch(path: string, options: RequestInit = {}) {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;

  // Phase 7: one request ID per call, sent as X-Request-ID. The backend
  // (main.py's RequestIDMiddleware) echoes it straight back in the
  // response rather than generating its own — so the SAME id shows up
  // in both this browser's network tab and the backend's structured
  // logs for this exact request. That's the actual "trace one request
  // across frontend -> backend" the roadmap asks for: not a shared
  // tracing backend, just one ID both sides agree to use and log.
  const requestId =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;

  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  headers.set("X-Request-ID", requestId);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.text();
    // Include the request ID in the thrown error too — surfaced by
    // error.tsx's "reference" line, so a person reporting a bug (or an
    // admin investigating one) has something exact to search backend
    // logs for, rather than "it broke sometime around 3pm."
    throw new Error(`API error ${res.status} [request_id=${requestId}]: ${body}`);
  }

  return res.json();
}
