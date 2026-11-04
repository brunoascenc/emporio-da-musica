from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

from src.langchain_layer.tools import build_store_tools
from src.services.store_queries import StoreDataError, StoreQueries, product_result, search_pattern


def test_search_treats_accents_and_sql_wildcards_as_literal_text():
    assert search_pattern("  VIOLÃO_100%!  ") == "%violao!_100!%!!%"


def test_price_rounding_preserves_cents():
    row = {
        "product_id": 1, "name": "Test", "description": "Test", "category_id": 1,
        "category": "Test", "price_brl": Decimal("0.05"), "discount_percent": Decimal("10"),
        "promotion_id": 1, "promotion_description": "Test", "status": "active",
        "stock_quantity": 1, "specs": {},
    }
    assert product_result(row)["price_brl"] == "0.05"


@pytest.mark.parametrize("name,arguments", [
    ("get_order", {"order_id": 1}),
    ("get_order", {"order_id": 1, "email": "invalid"}),
    ("get_product", {"product_id": -1}),
    ("search_products", {"limit": 21}),
    ("search_products", {"max_price_brl": "NaN"}),
    ("search_products", {"max_price_brl": "-1"}),
    ("search_products", {"sql": "SELECT * FROM customers"}),
])
def test_invalid_tool_inputs_do_not_reach_database(name, arguments):
    engine = MagicMock()
    tools = {tool.name: tool for tool in build_store_tools(engine)}
    response = tools[name].invoke(arguments)
    assert response.startswith("Invalid lookup arguments")
    engine.begin.assert_not_called()


def test_database_errors_are_sanitized_for_service_and_tool():
    engine = MagicMock()
    engine.begin.side_effect = OperationalError("private-email-and-password", {}, Exception("sensitive"))
    with pytest.raises(StoreDataError) as error:
        StoreQueries(engine).list_categories()
    assert "private" not in str(error.value)
    tool = build_store_tools(engine)[0]
    assert tool.invoke({}) == "Store data is temporarily unavailable. Please try again later."


def test_reads_use_read_only_transaction_and_bound_parameters():
    engine = MagicMock()
    connection = engine.begin.return_value.__enter__.return_value
    connection.execute.return_value.mappings.return_value.all.return_value = []
    StoreQueries(engine).search_products(query="'; DROP TABLE products; --")
    calls = connection.execute.call_args_list
    assert str(calls[0].args[0]) == "SET TRANSACTION READ ONLY"
    assert "DROP TABLE" not in str(calls[1].args[0])
    assert "DROP TABLE".lower() in calls[1].args[1]["query"]


def test_factory_exports_only_dedicated_lookup_tools():
    tools = build_store_tools(MagicMock())
    assert {tool.name for tool in tools} == {"list_categories", "search_products", "get_product", "get_order"}
    assert set(tools[-1].get_input_schema().model_json_schema()["required"]) == {"order_id", "email"}
