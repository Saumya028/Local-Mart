"use client";

import { useState } from "react";
import { uploadProductImage } from "@/lib/imageUpload";

export function ImageUploader({
  userId,
  images,
  onChange,
}: {
  userId: string;
  images: string[];
  onChange: (urls: string[]) => void;
}) {
  const [inputKey, setInputKey] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      // Sequential, not Promise.all — keeps upload order == display
      // order, which matters here since images[0] is used everywhere
      // (product cards, the variant-picker thumbnail) as THE thumbnail.
      const uploaded: string[] = [];
      for (const file of Array.from(files)) {
        uploaded.push(await uploadProductImage(userId, file));
      }
      onChange([...images, ...uploaded]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setUploading(false);
      setInputKey((k) => k + 1);
    }
  }

  function remove(i: number) {
    onChange(images.filter((_, idx) => idx !== i));
  }

  function moveToFront(i: number) {
    if (i === 0) return;
    const next = [...images];
    const [picked] = next.splice(i, 1);
    next.unshift(picked);
    onChange(next);
  }

  return (
    <div className="space-y-2">
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {images.map((url, i) => (
            <div key={`${url}-${i}`} className="relative group">
              {/* eslint-disable-next-line @next/next/no-img-element -- user-uploaded Supabase Storage URL, not a static asset */}
              <img
                src={url}
                alt=""
                className={`w-16 h-16 object-cover rounded-lg border ${i === 0 ? "border-blue-400 ring-1 ring-blue-400" : "border-gray-200"}`}
              />
              {i === 0 && (
                <span className="absolute -top-1.5 -left-1.5 bg-blue-600 text-white text-[9px] px-1 rounded">
                  Main
                </span>
              )}
              <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition rounded-lg flex items-center justify-center gap-1">
                {i !== 0 && (
                  <button
                    type="button"
                    onClick={() => moveToFront(i)}
                    title="Make main photo"
                    className="text-white text-[10px] bg-white/20 rounded px-1"
                  >
                    ★
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => remove(i)}
                  title="Remove"
                  className="text-white text-[10px] bg-white/20 rounded px-1"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2">
        <input
          key={inputKey}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          onChange={(e) => handleFiles(e.target.files)}
          disabled={uploading}
          className="text-sm border border-gray-200 rounded-lg px-2.5 py-1.5 file:mr-3 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:bg-blue-50 file:text-blue-700 file:text-xs disabled:opacity-50"
        />
        {uploading && <span className="text-xs text-gray-400">Uploading…</span>}
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
      <p className="text-xs text-gray-400">JPG, PNG or WEBP, up to 5MB each. First photo is used as the thumbnail.</p>
    </div>
  );
}
