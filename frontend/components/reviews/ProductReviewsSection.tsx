"use client";

import { ReviewList } from "./ReviewList";

export function ProductReviewsSection({
  productId,
  productName,
  shopName,
}: {
  productId: string;
  productName: string;
  shopName?: string | null;
}) {
  return <ReviewList kind="product" targetId={productId} targetName={productName} shopName={shopName} />;
}
