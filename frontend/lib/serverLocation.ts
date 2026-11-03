import { cookies } from "next/headers";

/** The delivery location the browser mirrored into the `lm_loc` cookie, if any. */
export async function getServerLocation(): Promise<{ lat: number; lng: number } | null> {
  const raw = (await cookies()).get("lm_loc")?.value;
  if (!raw) return null;
  const [a, b] = decodeURIComponent(raw).split(",").map(Number);
  if (!Number.isFinite(a) || !Number.isFinite(b) || Math.abs(a) > 90 || Math.abs(b) > 180) return null;
  return { lat: a, lng: b };
}
