const ICONS: Record<string, string> = {
  Groceries: "🥬",
  Grocery: "🥬",
  Bakery: "🥐",
  Pharmacy: "💊",
  Electronics: "📱",
  Fashion: "👗",
  Stationery: "✏️",
  "Home & Living": "🏠",
  Restaurants: "🍽️",
  Food: "🍽️",
};

const COLORS: Record<string, string> = {
  Groceries: "bg-emerald-50",
  Grocery: "bg-emerald-50",
  Bakery: "bg-amber-50",
  Pharmacy: "bg-red-50",
  Electronics: "bg-indigo-50",
  Fashion: "bg-pink-50",
  Stationery: "bg-orange-50",
  "Home & Living": "bg-teal-50",
  Restaurants: "bg-violet-50",
  Food: "bg-violet-50",
};

export function categoryIcon(category: string): string {
  return ICONS[category] ?? "🛍️";
}

export function categoryBg(category: string): string {
  return COLORS[category] ?? "bg-gray-50";
}
