"use client";

import { ReviewList } from "./ReviewList";

export function ShopReviewsSection({ shopId, shopName }: { shopId: string; shopName: string }) {
  return <ReviewList kind="shop" targetId={shopId} targetName={shopName} />;
}
