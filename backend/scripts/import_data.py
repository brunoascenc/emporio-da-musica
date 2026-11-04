import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from src.core.config import BACKEND_ROOT, Settings
from src.core.database import create_database_engine
from src.services.ingestion import IngestionError, import_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and atomically upsert the six operational CSV files.")
    parser.add_argument("--data-dir", type=Path, default=BACKEND_ROOT / "data")
    arguments = parser.parse_args()
    try:
        engine = create_database_engine(Settings())
    except ValidationError:
        print("Invalid database settings; check backend/.env.", file=sys.stderr)
        return 1
    try:
        counts = import_dataset(engine, arguments.data_dir)
    except IngestionError as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print(json.dumps({"status": "committed", "rows_processed": counts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
