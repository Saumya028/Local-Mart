import AuthStatus from "@/components/AuthStatus";

type HealthResponse = { api: string; database: string; redis: string };

async function getApiHealth(): Promise<HealthResponse> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/health`, { cache: "no-store" });
    if (!res.ok) throw new Error(`API responded with ${res.status}`);
    return res.json();
  } catch {
    return { api: "unreachable", database: "unknown", redis: "unknown" };
  }
}

/**
 * This page used to be the whole app ("/") back in Phase 0. Now that "/"
 * is the real Landing page, this connectivity check moves here — still
 * useful whenever something seems broken and you want to confirm the
 * basic wiring (API/DB/Redis/auth) before debugging further up the stack.
 */
export default async function DebugPage() {
  const health = await getApiHealth();

  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-6 p-8">
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-bold">System check</h1>
        <p className="text-gray-500 text-sm">Phase 0 + Phase 1 connectivity</p>
      </div>

      <div className="rounded-xl border border-gray-200 shadow-sm p-6 w-full max-w-sm space-y-3">
        <StatusRow label="Frontend → API" value={health.api} />
        <StatusRow label="API → Database" value={health.database} />
        <StatusRow label="API → Redis" value={health.redis} />
      </div>

      <div className="pt-2 border-t border-gray-100 w-full max-w-sm flex justify-center">
        <AuthStatus />
      </div>
    </main>
  );
}

function StatusRow({ label, value }: { label: string; value: string }) {
  const ok = value === "ok";
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-gray-600">{label}</span>
      <span className={`font-medium ${ok ? "text-green-600" : "text-red-500"}`}>{value}</span>
    </div>
  );
}
