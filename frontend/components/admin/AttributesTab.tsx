"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/apiClient";
import { AttributeField } from "@/lib/attributeSchema";

type SchemaRow = { id: string; kind: "product" | "shop"; category: string; fields: AttributeField[] };

const EMPTY_FIELD: AttributeField = { key: "", label: "", type: "text", required: false, options: [] };

export function AttributesTab() {
  const [schemas, setSchemas] = useState<SchemaRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<{ kind: "product" | "shop"; category: string } | null>(null);
  const [draftFields, setDraftFields] = useState<AttributeField[]>([]);
  const [saving, setSaving] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [newKind, setNewKind] = useState<"product" | "shop">("product");
  const [newCategory, setNewCategory] = useState("");

  async function load() {
    setLoading(true);
    try {
      const data: SchemaRow[] = await apiFetch("/admin/attribute-schemas");
      setSchemas(data);
      setError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function startEdit(row: SchemaRow) {
    setEditing({ kind: row.kind, category: row.category });
    setDraftFields(row.fields.length > 0 ? row.fields : [{ ...EMPTY_FIELD }]);
  }

  function startNew() {
    if (!newCategory.trim()) return;
    setEditing({ kind: newKind, category: newCategory.trim() });
    setDraftFields([{ ...EMPTY_FIELD }]);
    setShowNew(false);
    setNewCategory("");
  }

  async function save() {
    if (!editing) return;
    setSaving(true);
    setError(null);
    try {
      const cleanFields = draftFields
        .filter((f) => f.key.trim() && f.label.trim())
        .map((f) => ({
          ...f,
          options: f.type === "select" ? f.options.filter((o) => o.trim()) : [],
        }));
      await apiFetch(`/admin/attribute-schemas/${editing.kind}/${encodeURIComponent(editing.category)}`, {
        method: "PUT",
        body: JSON.stringify({ fields: cleanFields }),
      });
      setEditing(null);
      load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(row: SchemaRow) {
    if (!confirm(`Delete the schema for ${row.category} (${row.kind})? Existing products/shops keep their saved values — the form just stops asking for these fields.`)) {
      return;
    }
    try {
      await apiFetch(`/admin/attribute-schemas/${row.kind}/${encodeURIComponent(row.category)}`, {
        method: "DELETE",
      });
      load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  function updateDraftField(index: number, patch: Partial<AttributeField>) {
    setDraftFields((prev) => prev.map((f, i) => (i === index ? { ...f, ...patch } : f)));
  }

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Category Attributes</h2>
          <p className="text-sm text-gray-500 mt-1">
            Define the extra fields shops fill in per category — different fields for a grocery product than a
            pharmacy product, without a code change. Applies to both the Add Product form and the Apply to Sell
            form.
          </p>
        </div>
        <button
          onClick={() => setShowNew(!showNew)}
          className="bg-blue-600 text-white text-sm font-medium rounded-lg px-4 py-2 whitespace-nowrap"
        >
          {showNew ? "Cancel" : "+ New category schema"}
        </button>
      </div>

      {showNew && (
        <div className="flex flex-wrap items-center gap-2 border border-gray-100 bg-gray-50 rounded-xl p-4">
          <select
            value={newKind}
            onChange={(e) => setNewKind(e.target.value as "product" | "shop")}
            className="border border-gray-200 rounded-md px-3 py-2 text-sm bg-white"
          >
            <option value="product">Product fields</option>
            <option value="shop">Shop application fields</option>
          </select>
          <input
            placeholder="Category (e.g. Groceries) — must match what shops/products use"
            value={newCategory}
            onChange={(e) => setNewCategory(e.target.value)}
            className="flex-1 min-w-[240px] border border-gray-200 rounded-md px-3 py-2 text-sm bg-white"
          />
          <button onClick={startNew} className="bg-blue-600 text-white text-sm font-medium rounded-md px-4 py-2">
            Define fields
          </button>
        </div>
      )}

      {error && <p className="text-sm text-red-500">{error}</p>}

      {editing && (
        <div className="border border-blue-100 bg-blue-50/40 rounded-xl p-4 space-y-3">
          <p className="text-sm font-medium text-gray-900">
            {editing.category} — {editing.kind === "product" ? "Product fields" : "Shop application fields"}
          </p>

          <div className="space-y-2">
            {draftFields.map((field, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2 bg-white border border-gray-200 rounded-lg p-2">
                <input
                  placeholder="key (e.g. expiry_date)"
                  value={field.key}
                  onChange={(e) => updateDraftField(i, { key: e.target.value })}
                  className="w-40 border border-gray-200 rounded-md px-2 py-1.5 text-sm"
                />
                <input
                  placeholder="Label shown to users"
                  value={field.label}
                  onChange={(e) => updateDraftField(i, { label: e.target.value })}
                  className="w-48 border border-gray-200 rounded-md px-2 py-1.5 text-sm"
                />
                <select
                  value={field.type}
                  onChange={(e) => updateDraftField(i, { type: e.target.value as AttributeField["type"] })}
                  className="border border-gray-200 rounded-md px-2 py-1.5 text-sm"
                >
                  <option value="text">Text</option>
                  <option value="number">Number</option>
                  <option value="select">Select</option>
                  <option value="boolean">Yes/No</option>
                  <option value="date">Date</option>
                </select>
                {field.type === "select" && (
                  <input
                    placeholder="Options, comma-separated"
                    value={field.options.join(", ")}
                    onChange={(e) => updateDraftField(i, { options: e.target.value.split(",").map((o) => o.trim()) })}
                    className="flex-1 min-w-[180px] border border-gray-200 rounded-md px-2 py-1.5 text-sm"
                  />
                )}
                <label className="flex items-center gap-1.5 text-xs text-gray-600">
                  <input
                    type="checkbox"
                    checked={field.required}
                    onChange={(e) => updateDraftField(i, { required: e.target.checked })}
                  />
                  Required
                </label>
                <button
                  onClick={() => setDraftFields((prev) => prev.filter((_, idx) => idx !== i))}
                  className="text-red-400 hover:text-red-600 text-xs ml-auto"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setDraftFields((prev) => [...prev, { ...EMPTY_FIELD }])}
              className="text-sm text-blue-600 hover:underline"
            >
              + Add field
            </button>
            <div className="ml-auto flex gap-2">
              <button onClick={() => setEditing(null)} className="text-sm text-gray-500 px-3 py-1.5">
                Cancel
              </button>
              <button
                onClick={save}
                disabled={saving}
                className="bg-blue-600 text-white text-sm font-medium rounded-md px-4 py-1.5 disabled:opacity-50"
              >
                {saving ? "Saving…" : "Save schema"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white border border-gray-100 rounded-2xl overflow-hidden">
        {loading ? (
          <p className="text-sm text-gray-400 p-6">Loading…</p>
        ) : schemas.length === 0 ? (
          <p className="text-sm text-gray-400 p-6">No category schemas defined yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100 bg-gray-50/50">
                <th className="px-5 py-3 font-medium">Category</th>
                <th className="px-5 py-3 font-medium">Applies to</th>
                <th className="px-5 py-3 font-medium">Fields</th>
                <th className="px-5 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {schemas.map((row) => (
                <tr key={row.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/40">
                  <td className="px-5 py-3 font-medium text-gray-800">{row.category}</td>
                  <td className="px-5 py-3 text-gray-500 capitalize">{row.kind}</td>
                  <td className="px-5 py-3 text-gray-500">
                    {row.fields.length === 0 ? "—" : row.fields.map((f) => f.label).join(", ")}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <button onClick={() => startEdit(row)} className="text-blue-600 hover:underline text-xs">
                        Edit
                      </button>
                      <button onClick={() => remove(row)} className="text-red-400 hover:text-red-600 text-xs">
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
