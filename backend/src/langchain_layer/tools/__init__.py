"""Public factory for the agent's operational database tools."""

from langchain_core.tools import StructuredTool, ToolException
from sqlalchemy import Engine

from src.services.store_schemas import OrderLookup, ProductLookup, ProductSearch, ToolArguments
from src.services.store_queries import StoreDataError, StoreQueries


def build_store_tools(engine: Engine) -> list[StructuredTool]:
    queries = StoreQueries(engine)

    def wrap(handler):
        def invoke(**arguments):
            try:
                return handler(**arguments)
            except StoreDataError as error:
                raise ToolException(str(error)) from None
        return invoke

    definitions = (
        ("list_categories", queries.list_categories, ToolArguments, "List the store's instrument categories and IDs to refine a catalog search."),
        ("search_products", queries.search_products, ProductSearch, "Search instruments by name/model/category, budget, and availability. Returns bounded results sorted by current unit price. Prices include one active promotion, never additional payment discounts. Use has_more to refine searches."),
        ("get_product", queries.get_product, ProductLookup, "Look up a specific product's current price, active promotion, stock, status, and specifications. Check available before promising stock. Payment policies require a separate policy lookup."),
        ("get_order", queries.get_order, OrderLookup, "Look up order status and items only after obtaining BOTH its number and the customer's matching email. Returns no result for either missing order or mismatched email. Estimated delivery is not actual receipt; do not infer return eligibility."),
    )
    return [StructuredTool(
        name=name, func=wrap(handler), args_schema=schema, description=description,
        handle_tool_error=True,
        handle_validation_error="Invalid lookup arguments. Ask for the required details and use the tool's input schema.",
    ) for name, handler, schema, description in definitions]


__all__ = ["build_store_tools"]
