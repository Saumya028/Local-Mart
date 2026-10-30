"use client";

import { ChangeEvent, useState } from "react";
import { apiFetch } from "@/lib/apiClient";

type RowError = { line: number; sku: string | null; messages: string[] };
type ImportResult = {
  columns: string[];
  ignored_columns: string[];
  total_rows: number;
  to_create: number;
  to_update: number;
  errors: RowError[];
  applied: boolean;
  preview: { sku: string; action: "create" | "update"; name: string | null }[];
};

// Keep in sync with backend app/core/product_csv.py (COLUMNS / template_csv).
const TEMPLATE =
  "sku,name,price,category,stock_qty,description,mrp,unit_value,unit,barcode,gst_rate,hsn_code,low_stock_threshold,is_active\n" +
  "GHEE-1L,Amul Ghee,550,Grocery,40,Pure cow ghee,580,1,l,,12,04059020,5,yes\n" +
  "ATTA-5KG,Aashirvaad Atta,265,Grocery,25,,,5,kg,,0,,,yes\n";

function downloadTemplate() {
  const url = URL.createObjectURL(new Blob([TEMPLATE], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "localmart-products-template.csv";
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Bulk create/update products from a CSV. Two steps so nothing is saved by
 * surprise: choosing a file runs a dry run (validate + count what would be
 * created/updated, listing every bad row with its line number), and only an
 * error-free file can then be imported. Rows are matched by SKU.
 */
export function ProductImport({
  shopId,
  onClose,
  onImported,
}: {
  shopId: string;
  onClose: () => void;
  onImported: () => void;
}) {
  const [fileName, setFileName] = useState<string | null>(null);
  const [csvText, setCsvText] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(text: string, dryRun: boolean) {
    setBusy(true);
    setError(null);
    try {
      const res: ImportResult = await apiFetch("/dashboard/products/import", {
        method: "POST",
        body: JSON.stringify({ shop_id: shopId, csv_text: text, dry_run: dryRun }),
      });
      setResult(res);
      if (res.applied) onImported();
    } catch (err) {
      // apiFetch errors look like: API error 400 [request_id=…]: {"detail":"…"}
      const raw = (err as Error).message;
      const m = /"detail":"((?:[^"\\]|\\.)*)"/.exec(raw);
      setError(m ? m[1] : raw);
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setFileName(file.name);
    setResult(null);
    if (file.size > 2_500_000) {
      setError("That file is too large — upload up to about 2,000 products at a time.");
      return;
    }
    const text = await file.text();
    setCsvText(text);
    await run(text, true);
  }

  const ok = result && result.errors.length === 0 && result.to_create + result.to_update > 0;

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Import products from CSV</h2>
            <p className="text-sm text-gray-500">Add or update many products at once.</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700 text-xl leading-none" aria-label="Close">
            ✕
          </button>
        </div>

        {!result?.applied && (
          <>
            <ul className="text-sm text-gray-600 space-y-1 list-disc pl-5">
              <li>
                Rows are matched by <b>SKU</b>: an existing SKU is <b>updated</b> (blank cells are left unchanged), a new SKU
                is <b>created</b>.
              </li>
              <li>
                New products need <b>sku, name, price, category</b>. Price is <b>excluding GST</b>; <b>gst_rate</b> can be 0,
                0.25, 3, 5, 12, 18 or 28.
              </li>
              <li>If any row has a problem nothing is imported — fix the file and choose it again.</li>
              <li>Add photos afterwards by editing each product.</li>
            </ul>

            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={downloadTemplate}
                className="text-sm text-blue-600 hover:underline"
              >
                Download template
              </button>
              <label className="cursor-pointer border border-gray-200 rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
                {fileName ? "Choose a different file" : "Choose CSV file"}
                <input type="file" accept=".csv,text/csv" onChange={onFile} className="hidden" />
              </label>
              {fileName && <span className="text-sm text-gray-500 truncate">{fileName}</span>}
            </div>
          </>
        )}

        {busy && <p className="text-sm text-gray-500">Checking your file…</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}

        {result && !result.applied && (
          <div className="space-y-3">
            {result.ignored_columns.length > 0 && (
              <p className="text-xs text-amber-700">
                Ignored unknown columns: {result.ignored_columns.join(", ")}
              </p>
            )}
            {result.errors.length === 0 ? (
              <div className="rounded-lg bg-emerald-50 text-emerald-800 text-sm px-3 py-2">
                File looks good: <b>{result.to_create}</b> to create, <b>{result.to_update}</b> to update.
              </div>
            ) : (
              <div className="rounded-lg border border-red-100 bg-red-50 px-3 py-2 space-y-2">
                <p className="text-sm font-medium text-red-700">
                  {result.errors.length} of {result.total_rows} rows need fixing — nothing has been imported.
                </p>
                <ul className="text-sm text-red-700 space-y-1 max-h-56 overflow-y-auto">
                  {result.errors.slice(0, 100).map((e) => (
                    <li key={e.line}>
                      <b>Line {e.line}</b>
                      {e.sku ? ` (${e.sku})` : ""}: {e.messages.join("; ")}
                    </li>
                  ))}
                  {result.errors.length > 100 && <li>…and {result.errors.length - 100} more.</li>}
                </ul>
              </div>
            )}
            {result.preview.length > 0 && (
              <details className="text-sm text-gray-600">
                <summary className="cursor-pointer">Preview first {result.preview.length} valid rows</summary>
                <ul className="mt-2 space-y-0.5">
                  {result.preview.map((p) => (
                    <li key={p.sku}>
                      <span
                        className={`inline-block w-14 text-xs font-medium ${
                          p.action === "create" ? "text-emerald-700" : "text-blue-700"
                        }`}
                      >
                        {p.action === "create" ? "New" : "Update"}
                      </span>
                      {p.sku} — {p.name ?? ""}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            <div className="flex gap-2 justify-end">
              <button onClick={onClose} className="text-sm text-gray-500 px-3 py-2">
                Cancel
              </button>
              <button
                disabled={!ok || busy || !csvText}
                onClick={() => csvText && run(csvText, false)}
                className="bg-blue-600 text-white text-sm font-medium rounded-lg px-4 py-2 disabled:opacity-40"
              >
                {ok ? `Import ${result.to_create + result.to_update} products` : "Import"}
              </button>
            </div>
          </div>
        )}

        {result?.applied && (
          <div className="space-y-3">
            <div className="rounded-lg bg-emerald-50 text-emerald-800 text-sm px-3 py-2">
              Done — <b>{result.to_create}</b> created, <b>{result.to_update}</b> updated.
            </div>
            <div className="flex justify-end">
              <button onClick={onClose} className="bg-blue-600 text-white text-sm font-medium rounded-lg px-4 py-2">
                Close
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
