import { supabase } from "@/lib/supabaseClient";
import { prepareImage } from "@/lib/prepareImage";

// Public bucket, deliberately unlike shop-documents — product photos
// need to be viewable by any customer browsing the storefront, not just
// the signed-in owner. See frontend/README.md's "Product image storage
// setup" for the exact SQL to create it and its RLS policies.
export const PRODUCT_IMAGES_BUCKET = "product-images";


/**
 * Uploads one image to the product-images bucket under the current
 * user's own folder (`${userId}/...`) — required by the same
 * `storage.foldername(name))[1] = auth.uid()` RLS pattern used for shop
 * documents — and returns its permanent PUBLIC url. No signing needed
 * (unlike documentUpload.ts): the bucket itself is public, so the url
 * never expires and works for a logged-out customer too.
 */
export async function uploadProductImage(userId: string, file: File): Promise<string> {
  // Any image is accepted; it is resized/compressed to a small JPEG first.
  file = await prepareImage(file);

  const ext = "jpg";
  const path = `${userId}/${crypto.randomUUID()}.${ext}`;

  const { error: uploadError } = await supabase.storage
    .from(PRODUCT_IMAGES_BUCKET)
    .upload(path, file, { upsert: false, contentType: file.type });
  if (uploadError) {
    throw new Error(`Couldn't upload "${file.name}": ${uploadError.message}`);
  }

  const { data } = supabase.storage.from(PRODUCT_IMAGES_BUCKET).getPublicUrl(path);
  return data.publicUrl;
}
