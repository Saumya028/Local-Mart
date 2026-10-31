"use client";

import { useRef, useState } from "react";
import { uploadSupportPhoto } from "@/lib/supportUpload";

/** Up to `max` photos, uploaded straight to the private support-evidence bucket. */
export function EvidenceUploader({
  userId,
  photos,
  onChange,
  max,
}: {
  userId: string;
  photos: string[];
  onChange: (photos: string[]) => void;
  max: number;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pick(files: FileList | null) {
    if (!files || files.length === 0) return;
    setError(null);
    setBusy(true);
    try {
      const room = max - photos.length;
      const uploaded: string[] = [];
      for (const file of Array.from(files).slice(0, room)) {
        uploaded.push(await uploadSupportPhoto(userId, file));
      }
      onChange([...photos, ...uploaded]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        {photos.map((url) => (
          <div key={url} className="relative w-16 h-16 rounded-lg overflow-hidden border border-gray-200">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={url} alt="Evidence" className="w-full h-full object-cover" />
            <button
              type="button"
              aria-label="Remove photo"
              onClick={() => onChange(photos.filter((p) => p !== url))}
              className="absolute top-0.5 right-0.5 w-5 h-5 rounded-full bg-black/60 text-white text-xs leading-5"
            >
              ×
            </button>
          </div>
        ))}
        {photos.length < max && (
          <button
            type="button"
            onClick={() => input.current?.click()}
            disabled={busy}
            className="w-16 h-16 rounded-lg border border-dashed border-gray-300 text-gray-400 text-xs hover:border-blue-400 hover:text-blue-600 disabled:opacity-50"
          >
            {busy ? "…" : "+ Photo"}
          </button>
        )}
      </div>
      <input ref={input} type="file" accept="image/*" multiple className="hidden" onChange={(e) => pick(e.target.files)} />
      <p className="text-xs text-gray-400">
        {photos.length}/{max} photos
      </p>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}

export function PhotoStrip({ photos }: { photos: string[] }) {
  if (!photos || photos.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2 mt-2">
      {photos.map((url) => (
        <a key={url} href={url} target="_blank" rel="noreferrer" className="block w-16 h-16 rounded-lg overflow-hidden border border-gray-200">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt="Evidence" className="w-full h-full object-cover" />
        </a>
      ))}
    </div>
  );
}
