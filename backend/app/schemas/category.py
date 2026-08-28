from pydantic import BaseModel


class CategoryOut(BaseModel):
    name: str
    product_count: int
