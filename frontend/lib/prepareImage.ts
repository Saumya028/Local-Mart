// Phone cameras produce 3–12MB photos (and sometimes HEIC/AVIF). Rather than
// rejecting them, shrink every picked image in the browser before upload:
// scale the long edge down to MAX_EDGE and re-encode as JPEG. A typical
// 8MB photo becomes ~300–600KB, which is plenty for proof / product / QR
// images and uploads far faster on mobile data.

const MAX_EDGE = 1600;
const QUALITY = 0.85;
const MAX_INPUT_BYTES = 40 * 1024 * 1024; // sanity cap on what we'll even try to decode
const PASS_THROUGH_TYPES = ["image/jpeg", "image/png", "image/webp"];
const PASS_THROUGH_MAX = 5 * 1024 * 1024;

export async function prepareImage(file: File): Promise<File> {
  if (file.type && !file.type.startsWith("image/") && !/\.(heic|heif|avif)$/i.test(file.name)) {
    throw new Error(`"${file.name}" isn't an image — please choose a photo.`);
  }
  if (file.size > MAX_INPUT_BYTES) {
    throw new Error(`"${file.name}" is extremely large (over 40MB) — please choose a different photo.`);
  }

  try {
    // "from-image" applies the EXIF rotation, so portrait phone photos don't come out sideways.
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
    const w = Math.max(1, Math.round(bitmap.width * scale));
    const h = Math.max(1, Math.round(bitmap.height * scale));

    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("no canvas");
    ctx.fillStyle = "#fff"; // transparent PNGs would otherwise turn black as JPEG
    ctx.fillRect(0, 0, w, h);
    ctx.drawImage(bitmap, 0, 0, w, h);
    bitmap.close?.();

    const blob: Blob | null = await new Promise((res) => canvas.toBlob(res, "image/jpeg", QUALITY));
    if (!blob) throw new Error("encode failed");

    const base = file.name.replace(/\.[^.]+$/, "") || "photo";
    return new File([blob], `${base}.jpg`, { type: "image/jpeg" });
  } catch {
    // The browser couldn't decode it (e.g. HEIC in Chrome). If it's already a
    // normal small image just upload as-is; otherwise explain clearly.
    if (PASS_THROUGH_TYPES.includes(file.type) && file.size <= PASS_THROUGH_MAX) return file;
    throw new Error(
      `"${file.name}" couldn't be read by this browser. Try taking a photo with the camera, or choose a JPG/PNG.`
    );
  }
}
