from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, Json, StringConstraints, field_validator

Identifier = Annotated[int, Field(gt=0, le=2147483647)]
RequiredText = Annotated[str, StringConstraints(min_length=1, strip_whitespace=True)]
Money = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2, allow_inf_nan=False)]


class SourceRow(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CategoryRow(SourceRow):
    category_id: Identifier
    name: RequiredText
    description: RequiredText


class CustomerRow(SourceRow):
    customer_id: Identifier
    name: RequiredText
    phone: RequiredText
    email: RequiredText
    city: RequiredText


class ProductRow(SourceRow):
    product_id: Identifier
    price_brl: Money
    name: RequiredText
    category_id: Identifier
    description: RequiredText
    stock_quantity: Annotated[int, Field(ge=0, le=2147483647)]
    status: Literal["active", "coming_soon", "discontinued"]
    specs: Json[dict]
    created_at: date


class OrderRow(SourceRow):
    order_id: Identifier
    customer_id: Identifier
    order_date: date
    status: Literal["pending", "confirmed", "shipped", "delivered", "cancelled"]
    total_brl: Money
    payment_method: RequiredText
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None

    @field_validator("tracking_code", "estimated_delivery", "notes", mode="before")
    @classmethod
    def empty_is_null(cls, value):
        return None if value == "" else value


class OrderItemRow(SourceRow):
    order_id: Identifier
    quantity: Annotated[int, Field(gt=0, le=2147483647)]
    product_id: Identifier


class PromotionRow(SourceRow):
    promotion_id: Identifier
    product_id: Identifier
    discount_percent: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2, allow_inf_nan=False)]
    description: RequiredText
    is_active: bool

    @field_validator("is_active", mode="before")
    @classmethod
    def csv_boolean(cls, value):
        if value not in ("0", "1"):
            raise ValueError("Expected CSV boolean 0 or 1")
        return value == "1"
