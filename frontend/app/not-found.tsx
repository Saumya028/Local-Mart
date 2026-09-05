import Link from "next/link";

export default function NotFound() {
  return (
    <main className="max-w-md mx-auto px-6 py-16 text-center space-y-4">
      <h1 className="text-2xl font-bold">Page not found</h1>
      <p className="text-sm text-gray-500">
        The page you&rsquo;re looking for doesn&rsquo;t exist, or the link may be out of date.
      </p>
      <Link href="/" className="inline-block rounded-md bg-blue-600 text-white text-sm px-4 py-2">
        Back to LocalMart
      </Link>
    </main>
  );
}
