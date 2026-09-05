"use client";

/**
 * app/error.tsx (the normal error boundary) is rendered INSIDE
 * layout.tsx — so if layout.tsx itself throws (e.g. AuthProvider's
 * initial session check blowing up), that boundary never mounts at all.
 * global-error.tsx is the one Next.js convention that sits above the
 * root layout and catches that case specifically. It has to render its
 * own <html>/<body> since the real layout is exactly what may have
 * failed.
 */
export default function GlobalError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="bg-white text-gray-900">
        <main className="max-w-md mx-auto px-6 py-16 text-center space-y-4">
          <h1 className="text-2xl font-bold">Something went wrong</h1>
          <p className="text-sm text-gray-500">
            The app failed to load. Please try refreshing the page.
          </p>
          <button
            onClick={reset}
            className="inline-block rounded-md bg-blue-600 text-white text-sm px-4 py-2"
          >
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
