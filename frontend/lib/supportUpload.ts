import { supabase } from "@/lib/supabaseClient";
import { prepareImage } from "@/lib/prepareImage";

// Private bucket: evidence photos can show an address, a receipt or a
// customer's home, so (unlike product images) they are NOT publicly listable.
// Like shop documents, we upload under the user's own folder and store a
// long-lived signed link, which the customer, the shop and an admin can all
// open from the case. See frontend/README.md "Support evidence storage setup".
export const SUPPORT_EVIDENCE_BUCKET = "support-evidence";
const SIGNED_URL_TTL_SECONDS = 60 * 60 * 24 * 365 * 2;

export async function uploadSupportPhoto(userId: string, file: File): Promise<string> {
  file = await prepareImage(file); // resized/compressed JPEG
  const path = `${userId}/${crypto.randomUUID()}.jpg`;

  const { error } = await supabase.storage
    .from(SUPPORT_EVIDENCE_BUCKET)
    .upload(path, file, { upsert: false, contentType: file.type });
  if (error) throw new Error(`Couldn't upload "${file.name}": ${error.message}`);

  const { data, error: signError } = await supabase.storage
    .from(SUPPORT_EVIDENCE_BUCKET)
    .createSignedUrl(path, SIGNED_URL_TTL_SECONDS);
  if (signError || !data) throw new Error(`Uploaded "${file.name}" but couldn't create a link to it.`);
  return data.signedUrl;
}
