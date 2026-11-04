from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from openai import APIConnectionError
import pytest

from src.core.config import BACKEND_ROOT, Settings
from src.core.embeddings import DIMENSIONS, PolicyEmbeddings
from src.langchain_layer.tools.policies import build_policy_tool
from src.langchain_layer.vectorstore import vector_parameter
from src.services.policy_pdf import MAX_CHARS, PolicyError, extract_chunks, read_policy

POLICY_PATH = next((BACKEND_ROOT / "data").glob("*.pdf"))


def test_manual_sections_preserve_tables_pages_and_context():
    chunks = extract_chunks(read_policy(POLICY_PATH))
    by_section = {chunk.section: chunk for chunk in chunks}
    assert len(chunks) == 25
    hours = by_section["2"]
    assert hours.page_start == hours.page_end == 2
    assert "09:00" in hours.content and "18:00" in hours.content
    assert "PIX" in by_section["3"].content and "5%" in by_section["3"].content
    assert by_section["5.2"].page_start == by_section["5.2"].page_end == 5
    assert (by_section["7.2"].page_start, by_section["7.2"].page_end) == (6, 7)
    assert "8 Garantia" in by_section["8.1"].content
    assert all(len(chunk.content) <= MAX_CHARS for chunk in chunks)
    assert all("Manual de Pol\u00edticas e Procedimentos" not in chunk.content for chunk in chunks)


def test_long_sections_are_split_with_heading_context(monkeypatch):
    body = "1. Test section\n" + "A complete policy line.\n" * 400
    page = SimpleNamespace(extract_text=lambda **kwargs: body)
    monkeypatch.setattr("src.services.policy_pdf.PdfReader", lambda *args, **kwargs: SimpleNamespace(is_encrypted=False, pages=[page]))
    chunks = extract_chunks(b"test")
    assert len(chunks) > 1
    assert all(chunk.section == "1" and chunk.content.startswith("1 Test section\n") and len(chunk.content) <= MAX_CHARS for chunk in chunks)


def test_unreadable_pdf_is_rejected():
    with pytest.raises(PolicyError):
        extract_chunks(b"not a PDF")


def test_missing_pdf_is_rejected():
    with pytest.raises(PolicyError, match="Cannot read"):
        read_policy(Path("missing_policy.pdf"))


@pytest.mark.parametrize("vector", [[0.0] * DIMENSIONS, [1.0], [float("nan")] * DIMENSIONS, None])
def test_invalid_embedding_vectors_are_rejected(vector):
    with pytest.raises(PolicyError, match="invalid 1536"):
        vector_parameter(vector)


def test_missing_key_does_not_initialize_openai_client(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr("src.core.embeddings.OpenAI", client)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = Settings(_env_file=None, postgres_password="test", openai_api_key=None)
    with pytest.raises(PolicyError, match="Set OPENAI_API_KEY"):
        PolicyEmbeddings(settings).embed_query("Test query")
    client.assert_not_called()


def test_openai_adapter_batches_and_restores_response_order(monkeypatch):
    client = MagicMock()
    created = client.return_value.__enter__.return_value
    def embed(**kwargs):
        return SimpleNamespace(data=[SimpleNamespace(index=index, embedding=[float(index + 1)] * DIMENSIONS) for index in reversed(range(len(kwargs["input"])))])
    created.embeddings.create.side_effect = embed
    monkeypatch.setattr("src.core.embeddings.OpenAI", client)
    settings = Settings(_env_file=None, postgres_password="test", openai_api_key="test-key")
    vectors = PolicyEmbeddings(settings).embed_documents(["Test policy"] * 33)
    assert len(vectors) == 33
    assert vectors[0][0] == 1 and vectors[31][0] == 32
    assert created.embeddings.create.call_count == 2
    assert created.embeddings.create.call_args.kwargs["dimensions"] == DIMENSIONS


def test_provider_failure_is_sanitized(monkeypatch):
    client = MagicMock()
    client.return_value.__enter__.side_effect = APIConnectionError(request=MagicMock())
    monkeypatch.setattr("src.core.embeddings.OpenAI", client)
    settings = Settings(_env_file=None, postgres_password="test", openai_api_key="test-key")
    with pytest.raises(PolicyError, match="OpenAI embeddings are unavailable"):
        PolicyEmbeddings(settings).embed_query("Test query")


def test_policy_tool_validates_before_search_and_sanitizes_failures():
    store = MagicMock()
    tool = build_policy_tool(store)
    assert tool.invoke({"query": " "}).startswith("Provide a nonempty")
    store.search.assert_not_called()
    store.search.side_effect = PolicyError("Policy retrieval is unavailable.")
    assert tool.invoke({"query": "Opening hours"}) == "Policy retrieval is unavailable."
