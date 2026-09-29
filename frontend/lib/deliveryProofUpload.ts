import { supabase } from "@/lib/supabaseClient";

// Public bucket, same reasoning as product-images (see imageUpload.ts):
// a delivered order's proof photo is shown on the CUSTOMER's own order-
// tracking page too, not just inside the shop's dashboard, so it needs
// to be viewable without a signed Supabase session. See
// frontend/README.md's "Delivery proof photo storage setup" section for
// the exact SQL to create this bucket and its RLS policies.
export const DELIVERY_PROOFS_BUCKET = "delivery-proofs";

const MAX_FILE_BYTES = 5 * 1024 * 1024; // 5MB — a phone photo, not a full-res scan
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];

/**
 * Uploads one delivery-proof photo under the current (staff) user's own
 * folder — same `storage.foldername(name))[1] = auth.uid()` RLS pattern
 * as product-images — and returns its permanent public URL, ready to
 * pass straight to PATCH /dashboard/orders/{id}/status as
 * `delivery_proof_photo_url`.
 */
export async function uploadDeliveryProof(userId: string, file: File): Promise<string> {
  if (!ALLOWED_TYPES.includes(file.type)) {
    throw new Error(`"${file.name}" isn't a supported image type — use JPG, PNG, or WEBP.`);
  }
  if (file.size > MAX_FILE_BYTES) {
    throw new Error(`"${file.name}" is too large — proof photos must be under 5MB.`);
  }

  const ext = file.name.includes(".") ? file.name.split(".").pop() : "jpg";
  const path = `${userId}/${crypto.randomUUID()}.${ext}`;

  const { error: uploadError } = await supabase.storage
    .from(DELIVERY_PROOFS_BUCKET)
    .upload(path, file, { upsert: false, contentType: file.type });
  if (uploadError) {
    throw new Error(`Couldn't upload "${file.name}": ${uploadError.message}`);
  }

  const { data } = supabase.storage.from(DELIVERY_PROOFS_BUCKET).getPublicUrl(path);
  return data.publicUrl;
}
