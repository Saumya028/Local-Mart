import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t mt-16 py-8 text-sm text-gray-500">
      <div className="max-w-5xl mx-auto px-6 flex flex-wrap items-center justify-between gap-4">
        <p>&copy; {new Date().getFullYear()} LocalMart</p>
        <nav className="flex gap-6">
          <Link href="/privacy" className="hover:text-gray-900">
            Privacy Policy
          </Link>
          <Link href="/terms" className="hover:text-gray-900">
            Terms of Service
          </Link>
        </nav>
      </div>
    </footer>
  );
}
