from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Identifier = Annotated[int, Field(gt=0, le=2147483647)]


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductSearch(ToolArguments):
    query: str = Field(default="", max_length=200, description="Name, model, or category. Matching ignores case and common Portuguese accents.")
    category_id: Identifier | None = None
    max_price_brl: Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)] | None = Field(
        default=None, description="Maximum unit price after the active promotion, before payment-specific conditions."
    )
    only_available: bool = Field(default=True, description="Require active product status and positive stock.")
    limit: int = Field(default=5, ge=1, le=20)


class ProductLookup(ToolArguments):
    product_id: Identifier


class OrderLookup(ToolArguments):
    order_id: Identifier
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=254, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")]
