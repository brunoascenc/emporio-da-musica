"""Bounded, parameterized, read-only access to operational store data."""

from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
import unicodedata

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.services.store_schemas import OrderLookup, ProductLookup, ProductSearch

UNAVAILABLE_MESSAGE = "Store data is temporarily unavailable. Please try again later."
NOT_FOUND_ORDER = {"status": "not_found", "message": "No matching order was found for the supplied details."}

EFFECTIVE_PRICE = "round(p.price_brl * (100 - COALESCE(promo.discount_percent, 0)) / 100, 2)"
PRODUCT_SELECT = """
SELECT p.product_id, p.name, p.description, p.category_id, c.name AS category,
       p.price_brl, p.stock_quantity, p.status, p.specs,
       promo.promotion_id, promo.description AS promotion_description, promo.discount_percent
FROM products p
JOIN categories c ON c.category_id = p.category_id
LEFT JOIN LATERAL (
    SELECT promotion_id, description, discount_percent
    FROM promotions
    WHERE product_id = p.product_id AND is_active AND discount_percent > 0
    ORDER BY discount_percent DESC, promotion_id ASC
    LIMIT 1
) promo ON true
"""


class StoreDataError(RuntimeError):
    """A sanitized operational lookup failure."""


def search_pattern(query: str) -> str:
    normalized = "".join(character for character in unicodedata.normalize("NFD", query.strip().lower()) if not unicodedata.combining(character))
    return "%" + normalized.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


def product_result(row) -> dict:
    original = row["price_brl"]
    discount = row["discount_percent"] or Decimal("0")
    effective = (original * (Decimal("100") - discount) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    promotion = None
    if row["promotion_id"] is not None:
        promotion = {
            "promotion_id": row["promotion_id"],
            "description": row["promotion_description"],
            "discount_percent": format(discount, ".2f"),
        }
    return {
        "product_id": row["product_id"], "name": row["name"],
        "description": row["description"], "category_id": row["category_id"],
        "category": row["category"], "status": row["status"],
        "stock_quantity": row["stock_quantity"],
        "available": row["status"] == "active" and row["stock_quantity"] > 0,
        "original_price_brl": format(original, ".2f"),
        "price_brl": format(effective, ".2f"), "promotion": promotion,
        "specs": row["specs"],
    }


class StoreQueries:
    def __init__(self, engine: Engine):
        self.engine = engine

    @contextmanager
    def _read(self):
        try:
            with self.engine.begin() as connection:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                yield connection
        except SQLAlchemyError:
            raise StoreDataError(UNAVAILABLE_MESSAGE) from None

    def list_categories(self) -> dict:
        with self._read() as connection:
            rows = connection.execute(text("SELECT category_id, name, description FROM categories ORDER BY category_id LIMIT 100")).mappings().all()
        return {"status": "ok", "categories": [dict(row) for row in rows]}

    def search_products(self, **arguments) -> dict:
        request = ProductSearch(**arguments)
        conditions = ["translate(lower(concat_ws(' ', p.name, p.description, c.name)), '\u00e1\u00e0\u00e2\u00e3\u00e4\u00e9\u00e8\u00ea\u00eb\u00ed\u00ec\u00ee\u00ef\u00f3\u00f2\u00f4\u00f5\u00f6\u00fa\u00f9\u00fb\u00fc\u00e7', 'aaaaaeeeeiiiiooooouuuuc') LIKE :query ESCAPE '!'"]
        parameters = {"query": search_pattern(request.query), "limit": request.limit + 1}
        if request.category_id is not None:
            conditions.append("p.category_id = :category_id")
            parameters["category_id"] = request.category_id
        if request.max_price_brl is not None:
            conditions.append(f"{EFFECTIVE_PRICE} <= :budget")
            parameters["budget"] = request.max_price_brl
        if request.only_available:
            conditions.append("p.status = 'active' AND p.stock_quantity > 0")
        statement = text(PRODUCT_SELECT + " WHERE " + " AND ".join(conditions) + f" ORDER BY {EFFECTIVE_PRICE}, p.product_id LIMIT :limit")
        with self._read() as connection:
            rows = connection.execute(statement, parameters).mappings().all()
        return {"status": "ok", "products": [product_result(row) for row in rows[:request.limit]], "has_more": len(rows) > request.limit}

    def get_product(self, **arguments) -> dict:
        request = ProductLookup(**arguments)
        with self._read() as connection:
            row = connection.execute(text(PRODUCT_SELECT + " WHERE p.product_id = :product_id"), {"product_id": request.product_id}).mappings().one_or_none()
        if row is None:
            return {"status": "not_found", "message": "No matching product was found."}
        return {"status": "ok", "product": product_result(row)}

    def get_order(self, **arguments) -> dict:
        request = OrderLookup(**arguments)
        with self._read() as connection:
            order = connection.execute(text("""
                SELECT o.order_id, o.order_date, o.status, o.total_brl,
                       o.payment_method, o.tracking_code, o.estimated_delivery
                FROM orders o JOIN customers c ON c.customer_id = o.customer_id
                WHERE o.order_id = :order_id AND lower(trim(c.email)) = :email
            """), {"order_id": request.order_id, "email": request.email.lower()}).mappings().one_or_none()
            if order is None:
                return dict(NOT_FOUND_ORDER)
            items = connection.execute(text("""
                SELECT oi.product_id, p.name, oi.quantity
                FROM order_items oi JOIN products p ON p.product_id = oi.product_id
                WHERE oi.order_id = :order_id ORDER BY oi.product_id LIMIT 51
            """), {"order_id": request.order_id}).mappings().all()
        return {
            "status": "ok",
            "order": {
                "order_id": order["order_id"], "status": order["status"],
                "order_date": order["order_date"].isoformat(),
                "total_brl": format(order["total_brl"], ".2f"),
                "payment_method": order["payment_method"],
                "tracking_code": order["tracking_code"],
                "estimated_delivery": order["estimated_delivery"].isoformat() if order["estimated_delivery"] else None,
                "items": [dict(item) for item in items[:50]], "items_truncated": len(items) > 50,
            },
        }
