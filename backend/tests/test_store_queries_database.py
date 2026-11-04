import json
import os
from decimal import Decimal

import pytest
from sqlalchemy import text

from src.core.config import BACKEND_ROOT
from src.langchain_layer.tools import build_store_tools
from src.services.ingestion import import_dataset, load_dataset
from src.services.store_queries import NOT_FOUND_ORDER, StoreQueries
from test_ingestion_database import database_engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 to run PostgreSQL integration checks"),
]


@pytest.fixture
def store(database_engine):
    import_dataset(database_engine, BACKEND_ROOT / "data")
    return StoreQueries(database_engine)


def test_budget_category_and_accent_insensitive_search(store):
    result = store.search_products(query="VIOLAO", category_id=5, max_price_brl="1000.00", limit=20)
    assert result["products"]
    assert all(product["category_id"] == 5 and product["available"] and Decimal(product["price_brl"]) <= 1000 for product in result["products"])
    prices = [Decimal(product["price_brl"]) for product in result["products"]]
    assert prices == sorted(prices)
    assert len(store.list_categories()["categories"]) == 9


def test_unavailable_and_discontinued_products_are_explicit(store, database_engine):
    with database_engine.begin() as connection:
        connection.execute(text("UPDATE products SET stock_quantity=0 WHERE product_id=81"))
        connection.execute(text("UPDATE products SET status='discontinued' WHERE product_id=82"))
        connection.execute(text("UPDATE products SET status='coming_soon' WHERE product_id=83"))
    for product_id in (81, 82, 83):
        product = store.get_product(product_id=product_id)["product"]
        assert product["available"] is False
        assert not store.search_products(query=product["name"])["products"]
        assert store.search_products(query=product["name"], only_available=False)["products"]


def test_promotions_use_highest_active_discount_without_stacking(store, database_engine):
    assert store.get_product(product_id=93)["product"]["promotion"] is None
    assert store.get_product(product_id=94)["product"]["promotion"]["discount_percent"] == "8.00"
    with database_engine.begin() as connection:
        connection.execute(text("INSERT INTO promotions VALUES (999999,94,50,'Test active discount',true)"))
    product = store.get_product(product_id=94)["product"]
    assert product["promotion"]["discount_percent"] == "50.00"
    assert Decimal(product["price_brl"]) == Decimal(product["original_price_brl"]) / 2


def test_budget_uses_discounted_price_and_matching_rounding(store, database_engine):
    with database_engine.begin() as connection:
        connection.execute(text("UPDATE products SET price_brl=0.05 WHERE product_id=81"))
        connection.execute(text("INSERT INTO promotions VALUES (999999,81,50,'Test active discount',true)"))
    name = store.get_product(product_id=81)["product"]["name"]
    assert store.get_product(product_id=81)["product"]["price_brl"] == "0.03"
    assert store.search_products(query=name, max_price_brl="0.03")["products"]
    assert not store.search_products(query=name, max_price_brl="0.02")["products"]


def test_search_is_bounded_and_does_not_interpret_user_sql(store):
    response = store.search_products(limit=2)
    assert len(response["products"]) == 2
    assert response["has_more"] is True
    assert not store.search_products(query="%_")["products"]
    assert not store.search_products(query="'; DROP TABLE products; --")["products"]
    assert store.get_product(product_id=81)["status"] == "ok"
    assert store.get_product(product_id=999999)["status"] == "not_found"


def test_order_requires_matching_email_and_omits_private_fields(store):
    dataset = load_dataset(BACKEND_ROOT / "data")
    source_order = dataset["orders"][0]
    customer = next(row for row in dataset["customers"] if row["customer_id"] == source_order["customer_id"])
    response = store.get_order(order_id=source_order["order_id"], email="  " + customer["email"].upper() + "  ")
    assert response["status"] == "ok"
    assert response["order"]["status"] == source_order["status"]
    assert response["order"]["items"]
    assert not {"email", "phone", "customer_id", "notes", "name", "city"}.intersection(response["order"])
    assert customer["email"] not in json.dumps(response)
    assert store.get_order(order_id=source_order["order_id"], email="wrong@example.com") == NOT_FOUND_ORDER
    assert store.get_order(order_id=999999, email=customer["email"]) == NOT_FOUND_ORDER
    injection = "someone'OR'1'='1@example.com"
    assert store.get_order(order_id=source_order["order_id"], email=injection) == NOT_FOUND_ORDER


def test_langchain_tools_invoke_real_database_without_model_calls(store, database_engine):
    tools = {tool.name: tool for tool in build_store_tools(database_engine)}
    response = tools["search_products"].invoke({"query": "Yamaha C40"})
    assert response["products"][0]["product_id"] == 81
    assert tools["get_product"].invoke({"product_id": 81})["status"] == "ok"
    assert tools["get_order"].invoke({"order_id": 1, "email": "wrong@example.com"}) == NOT_FOUND_ORDER
