"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { uploadProductImage } from "@/lib/imageUpload";

type RowError = { line: number; sku: string | null; messages: string[] };
type ImportResult = {
  columns: string[];
  ignored_columns: string[];
  total_rows: number;
  to_create: number;
  to_update: number;
  errors: RowError[];
  applied: boolean;
  // File names the CSV refers to — the pictures that must be uploaded before importing.
  image_files: string[];
  variant_groups: { name: string; rows: number; options: string[] }[];
  preview: { sku: string; action: "create" | "update"; name: string | null; images: number | null; variant: string | null }[];
};

// Keep in sync with backend app/core/product_csv.py (COLUMNS / template_csv).
const TEMPLATE =
  "sku,name,price,category,stock_qty,description,mrp,unit_value,unit,barcode,gst_rate,hsn_code,low_stock_threshold,is_active,images,variant_group,variant_options\n" +
  "GHEE-1L,Amul Ghee,550,Grocery,40,Pure cow ghee,580,1,l,,12,04059020,5,yes,ghee-1l.jpg,,\n" +
  "ATTA-5KG,Aashirvaad Atta,265,Grocery,25,,,5,kg,,0,,,yes,atta-5kg.jpg|atta-5kg-back.jpg,,\n" +
  "OIL-500ML,Fortune Sunflower Oil,95,Grocery,40,Refined sunflower oil,105,500,ml,,5,15121910,5,yes,oil-500ml.jpg|oil-500ml-back.jpg,FORTUNE-OIL,\n" +
  "OIL-1L,Fortune Sunflower Oil,185,Grocery,25,Refined sunflower oil,205,1,l,,5,15121910,5,yes,oil-1l.jpg,FORTUNE-OIL,\n";

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
 *
 * Pictures: the CSV lists file names (images column); the seller selects those
 * image files here too. Nothing is uploaded until "Import" — then each needed
 * picture is uploaded once to the product-images bucket and the API receives the
 * resulting links. Variants: rows sharing a variant_group become one product
 * with a size/flavour picker.
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
  const { profile } = useAuth();
  const [images, setImages] = useState<File[]>([]);
  // The seller's choice: use every matching picture of a product, or only its first.
  const [imageMode, setImageMode] = useState<"all" | "first">("all");
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [csvText, setCsvText] = useState<string | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(
    text: string,
    dryRun: boolean,
    imageMap: Record<string, string> = {},
    names: string[] = images.map((f) => f.name),
    mode: "all" | "first" = imageMode,
  ) {
    setBusy(true);
    setError(null);
    try {
      const res: ImportResult = await apiFetch("/dashboard/products/import", {
        method: "POST",
        body: JSON.stringify({
          shop_id: shopId,
          csv_text: text,
          dry_run: dryRun,
          image_map: imageMap,
          image_names: names,
          image_mode: mode,
        }),
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

  function onImages(e: ChangeEvent<HTMLInputElement>) {
    const picked = Array.from(e.target.files ?? []).filter((f) => f.type.startsWith("image/") || /\.(jpe?g|png|webp|gif)$/i.test(f.name));
    e.target.value = "";
    if (picked.length === 0) return;
    setImages((prev) => {
      const byName = new Map(prev.map((f) => [f.name.toLowerCase(), f]));
      picked.forEach((f) => byName.set(f.name.toLowerCase(), f)); // picking a file again replaces it
      return Array.from(byName.values());
    });
  }

  // Pictures can be matched to products by SKU, so picking pictures (or changing the
  // one/several choice) after the CSV re-checks the file. Skipped on first render.
  const lastKey = useRef("");
  useEffect(() => {
    const key = `${imageMode}|${images.map((f) => f.name).join(",")}`;
    if (!csvText || result?.applied) {
      lastKey.current = key;
      return;
    }
    if (key === lastKey.current) return;
    lastKey.current = key;
    const t = setTimeout(() => {
      run(csvText, true);
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [images, imageMode, csvText]);

  // File names are matched ignoring case, exactly like the server does.
  const have = new Map(images.map((f) => [f.name.toLowerCase(), f]));
  const needed = result?.image_files ?? [];
  const neededLower = new Set(needed.map((n) => n.toLowerCase()));
  const missing = needed.filter((n) => !have.has(n.toLowerCase()));
  const unused = images.filter((f) => !neededLower.has(f.name.toLowerCase()));

  const ok = !!result && result.errors.length === 0 && result.to_create + result.to_update > 0 && missing.length === 0;

  async function doImport() {
    if (!csvText || !result || !profile) return;
    setBusy(true);
    setError(null);
    try {
      // Upload each needed picture once, a few at a time. If any fails we stop BEFORE
      // touching the catalogue, so nothing is half-imported.
      const map: Record<string, string> = {};
      const queue = [...needed];
      const total = queue.length;
      let done = 0;
      setProgress({ done, total });
      const worker = async () => {
        while (queue.length > 0) {
          const name = queue.shift() as string;
          map[name] = await uploadProductImage(profile.id, have.get(name.toLowerCase()) as File);
          done += 1;
          setProgress({ done, total });
        }
      };
      await Promise.all([worker(), worker(), worker()]);
      await run(csvText, false, map, images.map((f) => f.name), imageMode);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setProgress(null);
      setBusy(false);
    }
  }

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
              <li>
                <b>Pictures — one or several per product, your choice.</b> Either name the picture files after the{" "}
                <b>SKU</b> and leave the <b>images</b> column empty — <code>OIL-500ML.jpg</code> for one picture, or{" "}
                <code>OIL-500ML_1.jpg</code>, <code>OIL-500ML_2.jpg</code> … for several — or write the file names in the{" "}
                <b>images</b> column separated by <b>|</b> (e.g. <code>oil.jpg|oil-back.jpg</code>). Then select the picture
                files below. A filled <b>images</b> cell always wins over name matching.
              </li>
              <li>
                <b>Sizes / flavours:</b> give every row of the same product the same <b>variant_group</b> (e.g. an oil in 500
                ml and 1 l). Each row keeps its own SKU, price, stock and pictures. The size label is filled in from{" "}
                <b>unit_value</b> + <b>unit</b>, or write it in <b>variant_options</b> (e.g. <code>Size=500 ml</code>).
              </li>
              <li>If any row has a problem nothing is imported — fix the file and choose it again.</li>
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

            <div className="flex flex-wrap items-center gap-3">
              <label className="cursor-pointer border border-gray-200 rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
                Select pictures
                <input type="file" accept="image/*" multiple onChange={onImages} className="hidden" />
              </label>
              <label className="cursor-pointer border border-gray-200 rounded-lg px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
                Select a folder of pictures
                <input
                  type="file"
                  multiple
                  onChange={onImages}
                  className="hidden"
                  {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
                />
              </label>
              {images.length > 0 && <span className="text-sm text-gray-500">{images.length} picture{images.length === 1 ? "" : "s"} selected</span>}
            </div>

            <fieldset className="text-sm text-gray-700 space-y-1">
              <legend className="font-medium">Pictures per product</legend>
              <label className="flex items-start gap-2 cursor-pointer">
                <input type="radio" name="imageMode" checked={imageMode === "all"} onChange={() => setImageMode("all")} className="mt-1" />
                <span>
                  <b>Use all pictures</b> — a product gets every picture that matches it (up to 8)
                </span>
              </label>
              <label className="flex items-start gap-2 cursor-pointer">
                <input type="radio" name="imageMode" checked={imageMode === "first"} onChange={() => setImageMode("first")} className="mt-1" />
                <span>
                  <b>First picture only</b> — one picture per product, even if more files match
                </span>
              </label>
            </fieldset>
          </>
        )}

        {busy && !progress && <p className="text-sm text-gray-500">Working…</p>}
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
            {result.variant_groups.length > 0 && (
              <div className="rounded-lg border border-gray-100 px-3 py-2 text-sm text-gray-700 space-y-1">
                <p className="font-medium">
                  {result.variant_groups.length} product{result.variant_groups.length === 1 ? "" : "s"} with sizes/flavours
                </p>
                <ul className="space-y-0.5">
                  {result.variant_groups.map((g) => (
                    <li key={g.name}>
                      <b>{g.name}</b> — {g.options.join(" · ")}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {needed.length > 0 && (
              <div
                className={`rounded-lg px-3 py-2 text-sm ${
                  missing.length === 0 ? "bg-emerald-50 text-emerald-800" : "border border-amber-200 bg-amber-50 text-amber-800"
                }`}
              >
                {missing.length === 0 ? (
                  <>
                    All <b>{needed.length}</b> pictures are selected.
                  </>
                ) : (
                  <>
                    <b>{needed.length - missing.length}</b> of <b>{needed.length}</b> pictures selected. Still needed:{" "}
                    {missing.slice(0, 12).join(", ")}
                    {missing.length > 12 ? `, and ${missing.length - 12} more` : ""} — use <b>Select pictures</b> above.
                  </>
                )}
                {unused.length > 0 && <p className="text-xs mt-1 opacity-80">{unused.length} selected picture{unused.length === 1 ? " isn't" : "s aren't"} used by this file and will be skipped.</p>}
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
                      {p.variant && <span className="text-gray-400"> · {p.variant}</span>}
                      {p.images ? <span className="text-gray-400"> · {p.images} pic{p.images === 1 ? "" : "s"}</span> : null}
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
                onClick={doImport}
                className="bg-blue-600 text-white text-sm font-medium rounded-lg px-4 py-2 disabled:opacity-40"
              >
                {progress
                  ? `Uploading pictures ${progress.done}/${progress.total}…`
                  : ok
                    ? `Import ${result.to_create + result.to_update} products`
                    : "Import"}
              </button>
            </div>
          </div>
        )}

        {result?.applied && (
          <div className="space-y-3">
            <div className="rounded-lg bg-emerald-50 text-emerald-800 text-sm px-3 py-2">
              Done — <b>{result.to_create}</b> created, <b>{result.to_update}</b> updated
              {result.image_files.length > 0 && <>, <b>{result.image_files.length}</b> pictures uploaded</>}.
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
