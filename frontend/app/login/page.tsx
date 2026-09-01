"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // We call Supabase directly from the browser for auth — never through
  // our own backend. Supabase already handles password hashing, email
  // verification, and session/token issuing securely; re-implementing any
  // of that ourselves would be pure risk with no benefit.
  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const { error } =
      mode === "signin"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password });

    setLoading(false);

    if (error) {
      setError(error.message);
      return;
    }

    router.push("/");
    router.refresh();
  }

  return (
    <main className="min-h-screen flex items-center justify-center p-8">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 border border-gray-200 rounded-xl p-6 shadow-sm"
      >
        <h1 className="text-2xl font-bold text-center">
          {mode === "signin" ? "Log in" : "Create an account"}
        </h1>

        {mode === "signup" && (
          <p className="text-xs text-gray-500 text-center -mt-2">
            Every account starts as a customer. Selling on LocalMart
            requires your account to be approved by a platform admin
            afterward.
          </p>
        )}

        <input
          type="email"
          required
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <input
          type="password"
          required
          minLength={6}
          placeholder="Password (min 6 characters)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />

        {error && <p className="text-sm text-red-500">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-md py-2 text-sm font-medium disabled:opacity-50 transition"
        >
          {loading ? "Please wait…" : mode === "signin" ? "Log in" : "Sign up"}
        </button>

        <button
          type="button"
          onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
          className="w-full text-xs text-gray-500 underline"
        >
          {mode === "signin"
            ? "Need an account? Sign up"
            : "Already have an account? Log in"}
        </button>
      </form>
    </main>
  );
}
