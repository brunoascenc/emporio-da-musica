import argparse
import json
import sys

from pydantic import ValidationError

from src.core.config import Settings
from src.core.database import create_database_engine
from src.core.embeddings import PolicyEmbeddings
from src.langchain_layer.vectorstore import PolicyVectorStore
from src.services.policy_pdf import PolicyError


def main() -> int:
    parser = argparse.ArgumentParser(description="Retrieve policy passages and their references without a chat model.")
    parser.add_argument("query")
    arguments = parser.parse_args()
    try:
        settings = Settings()
    except ValidationError:
        print("Invalid settings; check backend/.env.", file=sys.stderr)
        return 1
    engine = create_database_engine(settings)
    try:
        result = PolicyVectorStore(engine, PolicyEmbeddings(settings), settings.embedding_model).search(query=arguments.query)
    except (PolicyError, ValidationError) as error:
        print(str(error) if isinstance(error, PolicyError) else "Provide a policy question between 2 and 1000 characters.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
