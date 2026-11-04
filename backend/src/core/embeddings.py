"""OpenAI embeddings with bounded requests and no client initialization until needed."""

from langchain_core.embeddings import Embeddings
from openai import OpenAI, OpenAIError

from src.core.config import Settings
from src.services.policy_pdf import PolicyError

DIMENSIONS = 1536


class PolicyEmbeddings(Embeddings):
    def __init__(self, settings: Settings):
        self.settings = settings

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        key = self.settings.openai_api_key
        if key is None or not key.get_secret_value().strip():
            raise PolicyError("Set OPENAI_API_KEY in backend/.env to embed or search policies.")
        vectors = []
        try:
            with OpenAI(api_key=key.get_secret_value(), timeout=30, max_retries=2) as client:
                for start in range(0, len(texts), 32):
                    batch = texts[start:start + 32]
                    response = client.embeddings.create(model=self.settings.embedding_model, dimensions=DIMENSIONS, input=batch)
                    ordered = sorted(response.data, key=lambda item: item.index)
                    if len(ordered) != len(batch) or [item.index for item in ordered] != list(range(len(batch))):
                        raise PolicyError("The embedding provider returned an incomplete response.")
                    vectors.extend(item.embedding for item in ordered)
        except OpenAIError:
            raise PolicyError("OpenAI embeddings are unavailable; check the API key, quota, and connection.") from None
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
