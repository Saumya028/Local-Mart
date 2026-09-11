from pydantic import BaseModel


class CategoryOut(BaseModel):
    name: str
    product_count: int
    # Counts DISTINCT shops in this category (is_active + approved), not
    # derived from product_count — a shop with zero products yet (just
    # approved, still stocking up) should still show up as a shop in its
    # category, and this is what the homepage's category cards display
    # ("85 shops"), not a product count.
    shop_count: int = 0
