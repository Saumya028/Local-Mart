import { supabase } from "@/lib/supabaseClient";

// Private bucket — see frontend/README.md's "Shop document storage
// setup" section for the exact SQL to create it and its RLS policies.
// Never made public: these files are ID proofs and business licenses.
export const SHOP_DOCUMENTS_BUCKET = "shop-documents";

// Long-lived (10 years) rather than short — the signed URL generated
// here is what gets stored in shops.documents and shown later to the
// owner and to admins reviewing the application; a URL that silently
// expired in an hour would leave a stored "document" that's actually a
// dead link the next time anyone opens it.
const SIGNED_URL_TTL_SECONDS = 60 * 60 * 24 * 365 * 10;

export type UploadedDocument = { name: string; doc_type: string; url: string };

/**
 * Uploads one file to the shop-documents bucket under the current
 * user's own folder (`${userId}/...`) — required for the RLS policy
 * (see README) that only lets an authenticated user write inside their
 * own folder — and returns a long-lived signed URL for it.
 *
 * `label` is the human-readable name the owner gave this document (e.g.
 * "GST Certificate"), separate from the underlying filename.
 */
export async function uploadShopDocument(
  userId: string,
  file: File,
  label: string,
  docType: string
): Promise<UploadedDocument> {
  const ext = file.name.includes(".") ? file.name.split(".").pop() : "";
  const path = `${userId}/${crypto.randomUUID()}${ext ? `.${ext}` : ""}`;

  const { error: uploadError } = await supabase.storage
    .from(SHOP_DOCUMENTS_BUCKET)
    .upload(path, file, { upsert: false, contentType: file.type || undefined });
  if (uploadError) {
    throw new Error(`Couldn't upload "${file.name}": ${uploadError.message}`);
  }

  const { data: signed, error: signError } = await supabase.storage
    .from(SHOP_DOCUMENTS_BUCKET)
    .createSignedUrl(path, SIGNED_URL_TTL_SECONDS);
  if (signError || !signed) {
    throw new Error(`Uploaded "${file.name}" but couldn't generate a link to it: ${signError?.message ?? "unknown error"}`);
  }

  return { name: label, doc_type: docType, url: signed.signedUrl };
}
