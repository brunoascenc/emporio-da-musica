"""Validate the supplied CSV snapshot and import it atomically."""

import csv
from pathlib import Path

from pydantic import ValidationError
from sqlalchemy import Engine, MetaData, Table
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from src.services.ingestion_schemas import (
    CategoryRow, CustomerRow, OrderItemRow, OrderRow, ProductRow, PromotionRow,
)

SOURCE_MODELS = {
    "categories": CategoryRow,
    "customers": CustomerRow,
    "products": ProductRow,
    "orders": OrderRow,
    "order_items": OrderItemRow,
    "promotions": PromotionRow,
}
PRIMARY_KEYS = {
    "categories": ("category_id",),
    "customers": ("customer_id",),
    "products": ("product_id",),
    "orders": ("order_id",),
    "order_items": ("order_id", "product_id"),
    "promotions": ("promotion_id",),
}
RELATIONSHIPS = (
    ("products", "category_id", "categories"),
    ("orders", "customer_id", "customers"),
    ("order_items", "order_id", "orders"),
    ("order_items", "product_id", "products"),
    ("promotions", "product_id", "products"),
)


class IngestionError(ValueError):
    """Actionable import error that does not include source row values."""


def load_dataset(data_dir: Path) -> dict[str, list[dict]]:
    dataset = {}
    for name, model in SOURCE_MODELS.items():
        filename = f"{name}.csv"
        rows = []
        seen = set()
        try:
            with (data_dir / filename).open(encoding="utf-8-sig", newline="") as source:
                reader = csv.DictReader(source, strict=True)
                headers = reader.fieldnames
                if headers is None or len(headers) != len(set(headers)) or set(headers) != set(model.model_fields):
                    raise IngestionError(f"{filename}: headers must match the expected columns exactly")
                for record_number, record in enumerate(reader, start=2):
                    if None in record or any(value is None for value in record.values()):
                        raise IngestionError(f"{filename}: record {record_number}: incorrect column count")
                    try:
                        row = model.model_validate(record).model_dump()
                    except ValidationError as error:
                        fields = ", ".join(sorted({str(item["loc"][0]) for item in error.errors()}))
                        raise IngestionError(f"{filename}: record {record_number}: invalid fields: {fields}") from None
                    key = tuple(row[column] for column in PRIMARY_KEYS[name])
                    if key in seen:
                        raise IngestionError(f"{filename}: record {record_number}: duplicate primary key")
                    seen.add(key)
                    rows.append(row)
        except (OSError, UnicodeError, csv.Error):
            raise IngestionError(f"{filename}: cannot read valid UTF-8 CSV data") from None
        dataset[name] = rows

    for child, column, parent in RELATIONSHIPS:
        parent_ids = {row[column] for row in dataset[parent]}
        for record_number, row in enumerate(dataset[child], start=2):
            if row[column] not in parent_ids:
                raise IngestionError(f"{child}.csv: record {record_number}: {column} references a missing {parent} row")
    return dataset


def import_dataset(engine: Engine, data_dir: Path) -> dict[str, int]:
    dataset = load_dataset(data_dir)
    active_table = "schema"
    try:
        with engine.begin() as connection:
            metadata = MetaData()
            for name, rows in dataset.items():
                active_table = name
                # Only the fixed source names above can be reflected or written.
                table = Table(name, metadata, autoload_with=connection)
                if not rows:
                    continue
                statement = insert(table)
                statement = statement.on_conflict_do_update(
                    index_elements=list(PRIMARY_KEYS[name]),
                    set_={column.name: statement.excluded[column.name] for column in table.columns if column.name not in PRIMARY_KEYS[name]},
                )
                connection.execute(statement, rows)
    except SQLAlchemyError:
        raise IngestionError(
            f"Database import failed at {active_table}; no changes committed. "
            "Check connectivity, apply migrations, and verify database constraints."
        ) from None
    return {name: len(rows) for name, rows in dataset.items()}
