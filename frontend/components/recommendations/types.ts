export type RecoSurface = "product" | "cart" | "home" | "buy_again";
export type RecoVariant = "model" | "baseline" | "holdout";

export type RecoItem = {
  id: string;
  shop_id: string;
  name: string;
  price: string;
  category: string;
  stock_qty: number;
  images: string[];
  rating_avg?: number | null;
  rating_count?: number | null;
  shop_name?: string | null;
  distance_km?: number | null;
  reason?: string | null;
};

export type RecoResponse = {
  surface: RecoSurface;
  run_id: string | null;
  variant: RecoVariant;
  items: RecoItem[];
};
