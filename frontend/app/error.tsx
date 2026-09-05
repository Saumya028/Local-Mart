"use client";

import { useEffect } from "react";

/**
 * Next.js App Router convention: automatically wraps every route
 * segment below it in an error boundary. Before this existed, any
 * unhandled error in a page component (e.g. apiFetch throwing because
 * the backend is down, or the Phase 7 catch-all exception handler on
 * the backend itself firing) showed Next's default, fairly alarming
 * dev-mode stack overlay — or, worse, a stock unstyled error page in
 * production. This is the roadmap's "a failed [...] fetch shouldn't
 * break the whole page" applied one level up: it shouldn't break the
 * whole APP either.
 */
export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Sentry, if configured (see sentry.client.config.ts), automatically
    // captures this via its React error-boundary integration — logging
    // here as well keeps a plain console record even when Sentry isn't
    // set up, e.g. in local dev.
    console.error("Unhandled error in route:", error);
  }, [error]);

  // apiClient.ts embeds `[request_id=...]` in thrown errors specifically
  // so it can be surfaced here — the one thing worth showing someone
  // reporting a bug, without dumping a raw stack trace in front of a
  // customer mid-checkout.
  const requestIdMatch = error.message.match(/request_id=([\w-]+)/);

  return (
    <main className="max-w-md mx-auto px-6 py-16 text-center space-y-4">
      <h1 className="text-2xl font-bold">Something went wrong</h1>
      <p className="text-sm text-gray-500">
        We hit an unexpected error. Trying again usually fixes it — if not, please check back
        shortly.
      </p>
      {requestIdMatch && (
        <p className="text-xs text-gray-400">
          Reference: <code>{requestIdMatch[1]}</code>
        </p>
      )}
      <button
        onClick={reset}
        className="inline-block rounded-md bg-blue-600 text-white text-sm px-4 py-2"
      >
        Try again
      </button>
    </main>
  );
}
