export type ReviewKind = "product" | "shop";

export type RatingSummary = {
  average: number;
  count: number;
  // "5".."1" -> number of reviews with that many stars
  distribution: Record<string, number>;
};

export type Review = {
  id: string;
  rating: number;
  title: string | null;
  body: string | null;
  reviewer_name: string;
  created_at: string;
  edited_at: string | null;
  reply_text: string | null;
  replied_at: string | null;
  verified_purchase: boolean;
};

export type ReviewList = { summary: RatingSummary; items: Review[]; total: number };

// The reviewer's own review (My Reviews tab / edit form).
export type MyReview = Review & {
  kind: ReviewKind;
  product_id: string | null;
  shop_id: string;
  target_name: string | null;
  target_image: string | null;
  is_hidden: boolean;
};

export type ReviewEligibility = { can_review: boolean; reason: string | null; review: MyReview | null };

export type PendingProduct = {
  product_id: string;
  product_name: string;
  image: string | null;
  shop_name: string | null;
  order_id: string;
};
export type PendingShop = { shop_id: string; shop_name: string; order_id: string };
export type MyReviewsResponse = {
  reviews: MyReview[];
  pending_products: PendingProduct[];
  pending_shops: PendingShop[];
};

// Shop owner side
export type DashboardReview = Review & {
  kind: ReviewKind;
  product_id: string | null;
  product_name: string | null;
  is_hidden: boolean;
  hidden_reason: string | null;
  hidden_at: string | null;
};
export type DashboardReviewList = { items: DashboardReview[]; total: number };
export type DashboardReviewSummary = {
  shop: RatingSummary;
  products: RatingSummary;
  unreplied_count: number;
  hidden_count: number;
};

// "/products/<id>/reviews..." or "/shops/<id>/reviews..."
export function reviewsPath(kind: ReviewKind, targetId: string): string {
  return `/${kind === "product" ? "products" : "shops"}/${targetId}/reviews`;
}

export function formatReviewDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
