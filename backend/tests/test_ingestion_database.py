"""Opt-in PostgreSQL checks in isolated, temporary schemas."""

import os
import uuid
from decimal import Decimal

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine, inspect, text

from src.core.config import BACKEND_ROOT, Settings
from src.core.database import create_database_engine
from src.services.ingestion import IngestionError, import_dataset
from test_ingestion import EXPECTED_COUNTS, rewrite_csv, source_dir 

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 to run PostgreSQL integration checks"),
]


@pytest.fixture
def database_engine():
    settings = Settings()
    admin = create_database_engine(settings)
    schema = f"ingestion_test_{uuid.uuid4().hex}"
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(settings.database_url, connect_args={"connect_timeout": 3, "options": f"-c search_path={schema}"})
    try:
        configuration = Config(str(BACKEND_ROOT / "alembic.ini"))
        with engine.begin() as connection:
            configuration.attributes["connection"] = connection
            command.upgrade(configuration, "head")
            command.upgrade(configuration, "head")
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def counts(engine):
    with engine.connect() as connection:
        return {name: connection.scalar(text(f'SELECT count(*) FROM "{name}"')) for name in EXPECTED_COUNTS}


def test_migrations_and_repeat_import_preserve_typed_data(database_engine, source_dir):
    assert import_dataset(database_engine, source_dir) == EXPECTED_COUNTS
    assert import_dataset(database_engine, source_dir) == EXPECTED_COUNTS
    assert counts(database_engine) == EXPECTED_COUNTS
    with database_engine.connect() as connection:
        row = connection.execute(text("SELECT price_brl, specs, created_at FROM products WHERE product_id = 81")).one()
        assert row.price_brl == Decimal("599.90")
        assert row.specs["strings"] == "nylon"
        assert row.created_at.isoformat() == "2021-03-15"
        assert connection.scalar(text("SELECT count(*) FROM promotions WHERE is_active")) == 4
        assert connection.scalar(text("SELECT count(*) FROM orders WHERE estimated_delivery IS NULL")) == 12
    inspector = inspect(database_engine)
    assert set(inspector.get_pk_constraint("order_items")["constrained_columns"]) == {"order_id", "product_id"}
    assert sum(len(inspector.get_foreign_keys(table)) for table in EXPECTED_COUNTS) == 5


def test_repeat_import_updates_existing_rows(database_engine, source_dir):
    import_dataset(database_engine, source_dir)
    rewrite_csv(source_dir / "products.csv", lambda rows: rows[0].update(price_brl="123.45"))
    import_dataset(database_engine, source_dir)
    assert counts(database_engine) == EXPECTED_COUNTS
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT price_brl FROM products WHERE product_id = 81")) == Decimal("123.45")


def test_late_database_failure_rolls_back_all_tables(database_engine, source_dir):
    import_dataset(database_engine, source_dir)
    with database_engine.begin() as connection:
        original = connection.scalar(text("SELECT name FROM categories WHERE category_id = 1"))
        connection.exec_driver_sql("""
            CREATE FUNCTION reject_promotion() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Simulated late import failure'; END; $$;
        """)
        connection.exec_driver_sql("CREATE TRIGGER reject_import BEFORE INSERT OR UPDATE ON promotions FOR EACH ROW EXECUTE FUNCTION reject_promotion()")
    rewrite_csv(source_dir / "categories.csv", lambda rows: rows[0].update(name="Should roll back"))
    with pytest.raises(IngestionError, match="no changes committed"):
        import_dataset(database_engine, source_dir)
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT name FROM categories WHERE category_id = 1")) == original
    assert counts(database_engine) == EXPECTED_COUNTS
