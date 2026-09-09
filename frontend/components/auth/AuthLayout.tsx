import Link from "next/link";
import { ReactNode } from "react";

const STATS = [
  { value: "2,400+", label: "Local shops" },
  { value: "180K+", label: "Happy customers" },
  { value: "15 min", label: "Avg delivery" },
];

export function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col md:flex-row">
      <div className="md:w-1/2 bg-gradient-to-br from-blue-600 to-blue-500 text-white px-8 py-12 md:py-20 flex flex-col justify-center">
        <div className="max-w-md mx-auto md:mx-0 space-y-8">
          <div className="flex items-center gap-2">
            <span className="w-9 h-9 rounded-lg bg-white/20 flex items-center justify-center">
              <svg viewBox="0 0 20 20" fill="none" className="w-5 h-5">
                <path d="M10 2 2.5 6v8L10 18l7.5-4V6L10 2Z" stroke="white" strokeWidth="1.4" fill="white" fillOpacity={0.2} />
              </svg>
            </span>
            <span className="text-lg font-bold">LocalMart</span>
          </div>

          <div className="space-y-3">
            <h1 className="text-3xl sm:text-4xl font-bold leading-tight">Your neighborhood, delivered to your door</h1>
            <p className="text-blue-100">
              Shop from 2,400+ local stores. Fresh products, fast delivery, and the joy of supporting your community.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-3">
            {STATS.map((s) => (
              <div key={s.label} className="bg-white/10 rounded-xl px-3 py-4 text-center sm:text-left">
                <p className="text-lg sm:text-xl font-bold">{s.value}</p>
                <p className="text-xs text-blue-100 mt-0.5">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="md:w-1/2 px-6 sm:px-12 py-10 flex flex-col justify-center bg-gradient-to-br from-white to-emerald-50">
        <div className="max-w-sm mx-auto w-full space-y-6">
          <Link href="/" className="text-sm text-gray-500 hover:text-gray-800 inline-flex items-center gap-1">
            ← Back to home
          </Link>

          <div>
            <h2 className="text-2xl font-bold text-gray-900">{title}</h2>
            <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
          </div>

          {children}
        </div>
      </div>
    </div>
  );
}
