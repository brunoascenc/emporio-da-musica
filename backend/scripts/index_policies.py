import argparse
import json
from pathlib import Path
import sys

from pydantic import ValidationError

from src.core.config import BACKEND_ROOT, Settings
from src.core.database import create_database_engine
from src.core.embeddings import PolicyEmbeddings
from src.langchain_layer.vectorstore import PolicyVectorStore
from src.services.policy_pdf import PolicyError


def main() -> int:
    parser = argparse.ArgumentParser(description="Index the store policy PDF only when its content or embedding configuration changes.")
    parser.add_argument("--pdf", type=Path, default=BACKEND_ROOT / "data" / "pol\u00edticas_da_loja.pdf")
    arguments = parser.parse_args()
    try:
        settings = Settings()
    except ValidationError:
        print("Invalid settings; check backend/.env.", file=sys.stderr)
        return 1
    engine = create_database_engine(settings)
    try:
        result = PolicyVectorStore(engine, PolicyEmbeddings(settings), settings.embedding_model).ingest(arguments.pdf)
    except PolicyError as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
