import csv
from datetime import date
from decimal import Decimal
from pathlib import Path
import shutil

import pytest

from src.core.config import BACKEND_ROOT
from src.services.ingestion import IngestionError, load_dataset

EXPECTED_COUNTS = {"categories": 9, "customers": 50, "products": 65, "orders": 20, "order_items": 22, "promotions": 25}


@pytest.fixture
def source_dir(tmp_path):
    destination = tmp_path / "data"
    shutil.copytree(BACKEND_ROOT / "data", destination)
    return destination


def rewrite_csv(path: Path, transform):
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fields, rows = reader.fieldnames, list(reader)
    transform(rows)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_supplied_dataset_is_typed_and_complete():
    dataset = load_dataset(BACKEND_ROOT / "data")
    assert {name: len(rows) for name, rows in dataset.items()} == EXPECTED_COUNTS
    assert dataset["products"][0]["price_brl"] == Decimal("599.9")
    assert isinstance(dataset["products"][0]["created_at"], date)
    assert isinstance(dataset["products"][0]["specs"], dict)
    assert sum(row["is_active"] for row in dataset["promotions"]) == 4
    assert sum(row["estimated_delivery"] is None for row in dataset["orders"]) == 12


@pytest.mark.parametrize("table", ["categories", "order_items"])
def test_duplicate_keys_are_rejected(source_dir, table):
    rewrite_csv(source_dir / f"{table}.csv", lambda rows: rows.append(rows[0].copy()))
    with pytest.raises(IngestionError, match="duplicate primary key"):
        load_dataset(source_dir)


@pytest.mark.parametrize("table,column,value", [
    ("products", "specs", "[]"),
    ("products", "price_brl", "NaN"),
    ("products", "price_brl", "12.345"),
    ("products", "stock_quantity", "-1"),
    ("orders", "order_date", "not-a-date"),
    ("promotions", "discount_percent", "101"),
    ("promotions", "is_active", "yes"),
])
def test_invalid_field_reports_location_without_value(source_dir, table, column, value):
    rewrite_csv(source_dir / f"{table}.csv", lambda rows: rows[0].update({column: value}))
    with pytest.raises(IngestionError) as error:
        load_dataset(source_dir)
    assert str(error.value) == f"{table}.csv: record 2: invalid fields: {column}"


def test_missing_reference_is_rejected(source_dir):
    rewrite_csv(source_dir / "promotions.csv", lambda rows: rows[0].update(product_id="999999"))
    with pytest.raises(IngestionError, match="product_id references a missing products row"):
        load_dataset(source_dir)


def test_missing_file_is_reported(source_dir):
    (source_dir / "customers.csv").unlink()
    with pytest.raises(IngestionError, match="customers.csv: cannot read"):
        load_dataset(source_dir)


def test_bad_headers_are_rejected(source_dir):
    (source_dir / "customers.csv").write_text("customer_id,customer_id\n1,1\n", encoding="utf-8")
    with pytest.raises(IngestionError, match="headers must match"):
        load_dataset(source_dir)


def test_incomplete_record_is_rejected(source_dir):
    (source_dir / "categories.csv").write_text("category_id,name,description\n1,Name\n", encoding="utf-8")
    with pytest.raises(IngestionError, match="incorrect column count"):
        load_dataset(source_dir)
