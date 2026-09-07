"use client";

import { useState } from "react";
import { uploadShopDocument, UploadedDocument } from "@/lib/documentUpload";
import { DOCUMENT_TYPES, documentTypeLabel } from "@/lib/documentTypes";

export function DocumentUploader({
  userId,
  documents,
  onChange,
}: {
  userId: string;
  documents: UploadedDocument[];
  onChange: (docs: UploadedDocument[]) => void;
}) {
  const [docType, setDocType] = useState(DOCUMENT_TYPES[0].value);
  const [file, setFile] = useState<File | null>(null);
  const [inputKey, setInputKey] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAdd() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const label = documentTypeLabel(docType);
      const doc = await uploadShopDocument(userId, file, label, docType);
      onChange([...documents, doc]);
      setFile(null);
      setInputKey((k) => k + 1); // remounts the file input so its displayed filename clears
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
    }
  }

  function remove(i: number) {
    onChange(documents.filter((_, idx) => idx !== i));
  }

  return (
    <div className="space-y-3">
      {documents.length > 0 && (
        <ul className="space-y-1.5">
          {documents.map((d, i) => (
            <li
              key={`${d.url}-${i}`}
              className="flex items-center justify-between text-sm bg-gray-50 border border-gray-100 rounded-lg px-3 py-2"
            >
              <a href={d.url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline truncate">
                {d.name}
              </a>
              <button type="button" onClick={() => remove(i)} className="text-xs text-red-500 ml-3 shrink-0">
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-col sm:flex-row gap-2">
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          className="border border-gray-200 rounded-lg px-2.5 py-2 text-sm sm:w-56 shrink-0 bg-white"
        >
          {DOCUMENT_TYPES.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </select>
        <input
          key={inputKey}
          type="file"
          accept="application/pdf,image/*"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="flex-1 text-sm border border-gray-200 rounded-lg px-2.5 py-1.5 file:mr-3 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:bg-blue-50 file:text-blue-700 file:text-xs"
        />
        <button
          type="button"
          onClick={handleAdd}
          disabled={!file || uploading}
          className="text-sm font-medium bg-gray-900 text-white rounded-lg px-4 py-2 disabled:opacity-40 whitespace-nowrap"
        >
          {uploading ? "Uploading…" : "+ Add"}
        </button>
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <p className="text-xs text-gray-400">PDF or image, one file per document.</p>
    </div>
  );
}
