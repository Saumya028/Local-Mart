import { DAY_KEYS, DAY_LABELS, OpenInfo, OpeningHours, ShopTerms, DEFAULT_TZ, deliveryTerms, rangesText, todayKey } from "@/lib/shopInfo";
import { ShopStatusBadge } from "./ShopStatusBadge";

export type PublicShopInfo = ShopTerms & {
  contact_phone?: string | null;
  description?: string | null;
  opening_hours?: OpeningHours | null;
  timezone?: string;
  open_info?: OpenInfo | null;
  slots_enabled?: boolean;
  address_line1?: string | null;
  city?: string | null;
};

/** "+919820012345" -> "+91 98200 12345" */
function prettyPhone(p: string): string {
  const m = p.match(/^\+91(\d{5})(\d{5})$/);
  return m ? `+91 ${m[1]} ${m[2]}` : p;
}

/** Everything a customer wants to know before ordering: is it open, how to
 *  reach the shop, its hours, and what delivery costs. Server-renderable. */
export function ShopInfoPanel({ shop }: { shop: PublicShopInfo }) {
  const tz = shop.timezone || DEFAULT_TZ;
  const info = shop.open_info;
  const terms = deliveryTerms(shop);
  const today = todayKey(tz);

  return (
    <section aria-label="Shop information" className="border border-gray-100 rounded-2xl p-5 grid gap-5 md:grid-cols-2">
      <div className="space-y-3">
        <ShopStatusBadge info={info} timezone={tz} />
        {info && !info.is_open && info.state === "temporarily_closed" && info.message && (
          <p className="text-sm text-amber-700">“{info.message}”</p>
        )}
        {info && !info.is_open && (
          <p className="text-xs text-gray-500">
            You can still add items to your cart
            {shop.slots_enabled ? " and schedule a delivery or pickup time slot at checkout." : ", but you can only place the order once the shop is open."}
          </p>
        )}
        {shop.description && <p className="text-sm text-gray-700 whitespace-pre-line">{shop.description}</p>}
        {shop.contact_phone && (
          <p className="text-sm">
            <span className="text-gray-500">Call: </span>
            <a href={`tel:${shop.contact_phone}`} className="text-blue-600 font-medium hover:underline">
              {prettyPhone(shop.contact_phone)}
            </a>
          </p>
        )}
        {shop.address_line1 && (
          <p className="text-sm text-gray-500">
            {shop.address_line1}
            {shop.city ? `, ${shop.city}` : ""}
          </p>
        )}
        <div className="flex flex-wrap gap-1.5 pt-1">
          {terms.map((t) => (
            <span key={t} className="text-xs bg-gray-50 border border-gray-100 text-gray-700 rounded-full px-2.5 py-1">
              {t}
            </span>
          ))}
          {shop.prep_time_minutes != null && (
            <span className="text-xs bg-gray-50 border border-gray-100 text-gray-700 rounded-full px-2.5 py-1">
              Ready in ~{shop.prep_time_minutes} min
            </span>
          )}
          {shop.slots_enabled && (
            <span className="text-xs bg-blue-50 border border-blue-100 text-blue-700 rounded-full px-2.5 py-1">Time slots available</span>
          )}
        </div>
      </div>

      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-400 mb-2">Opening hours</p>
        {shop.opening_hours ? (
          <table className="w-full text-sm">
            <tbody>
              {DAY_KEYS.map((d) => (
                <tr key={d} className={d === today ? "font-semibold text-gray-900" : "text-gray-600"}>
                  <td className="py-0.5 pr-4 whitespace-nowrap">{DAY_LABELS[d]}</td>
                  <td className="py-0.5">{rangesText(shop.opening_hours?.[d])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-gray-500">This shop hasn’t published opening hours — call to check before you visit.</p>
        )}
      </div>
    </section>
  );
}
