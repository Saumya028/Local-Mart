// Shown instantly while the product page's server render + API call finish,
// so navigation feels immediate instead of freezing on the previous page.
export default function Loading() {
  return (
    <main className="max-w-5xl mx-auto px-6 py-10" aria-busy="true">
      <div className="grid md:grid-cols-2 gap-10 animate-pulse">
        <div className="aspect-square rounded-xl bg-gray-100" />
        <div className="space-y-4">
          <div className="h-3 w-16 rounded bg-gray-100" />
          <div className="h-7 w-2/3 rounded bg-gray-100" />
          <div className="h-7 w-24 rounded bg-gray-100" />
          <div className="h-4 w-full rounded bg-gray-100" />
          <div className="h-4 w-5/6 rounded bg-gray-100" />
          <div className="h-10 w-32 rounded-lg bg-gray-100" />
        </div>
      </div>
    </main>
  );
}
