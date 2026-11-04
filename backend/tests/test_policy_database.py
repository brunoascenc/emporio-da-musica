from hashlib import sha256
import os

from langchain_core.embeddings import Embeddings
import pytest
from sqlalchemy import text

from src.core.embeddings import DIMENSIONS
from src.langchain_layer.tools.policies import build_policy_tool
from src.langchain_layer.vectorstore import PolicyVectorStore
from src.services.policy_pdf import PolicyError
from test_ingestion_database import database_engine
from test_policies import POLICY_PATH

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="Set RUN_DB_TESTS=1 to run PostgreSQL integration checks"),
]


class RecordingEmbeddings(Embeddings):
    """Deterministic vectors exercise storage and similarity, not semantic quality."""
    def __init__(self):
        self.document_calls = 0
        self.query_calls = 0

    @staticmethod
    def vector(value):
        vector = [0.0] * DIMENSIONS
        vector[int.from_bytes(sha256(value.encode()).digest()[:2]) % DIMENSIONS] = 1.0
        return vector

    def embed_documents(self, texts):
        self.document_calls += 1
        return [self.vector(value) for value in texts]

    def embed_query(self, value):
        self.query_calls += 1
        return self.vector(value)


def test_repeat_ingestion_skips_provider_and_returns_references(database_engine):
    embeddings = RecordingEmbeddings()
    store = PolicyVectorStore(database_engine, embeddings, "test-model")
    first = store.ingest(POLICY_PATH)
    assert first["status"] == "indexed" and first["chunks"] == 25
    assert store.ingest(POLICY_PATH)["status"] == "unchanged"
    assert embeddings.document_calls == 1
    with database_engine.connect() as connection:
        content = connection.scalar(text("SELECT content FROM policy_chunks WHERE section='3.1' LIMIT 1"))
    result = build_policy_tool(store).invoke({"query": content[:1000], "limit": 1})
    assert result["context_only"] is True
    assert len(result["passages"]) <= 3
    assert all(row["source_name"] == POLICY_PATH.name and row["page_start"] > 0 and len(row["file_hash"]) == 64 for row in result["passages"])
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM policy_chunks")) == 25


def test_unindexed_store_does_not_call_provider(database_engine):
    embeddings = RecordingEmbeddings()
    result = PolicyVectorStore(database_engine, embeddings, "test-model").search(query="Opening hours")
    assert result["status"] == "not_indexed" and not result["passages"]
    assert embeddings.query_calls == 0


def test_changed_source_failure_preserves_previous_index(database_engine, tmp_path):
    embeddings = RecordingEmbeddings()
    store = PolicyVectorStore(database_engine, embeddings, "test-model")
    store.ingest(POLICY_PATH)
    changed = tmp_path / POLICY_PATH.name
    changed.write_bytes(POLICY_PATH.read_bytes() + b"\n%Changed metadata\n")
    embeddings.embed_documents = lambda texts: (_ for _ in ()).throw(PolicyError("Provider unavailable"))
    with pytest.raises(PolicyError, match="Provider unavailable"):
        store.ingest(changed)
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT file_hash FROM policy_documents")) == sha256(POLICY_PATH.read_bytes()).hexdigest()
        assert connection.scalar(text("SELECT count(*) FROM policy_chunks")) == 25


def test_new_configuration_and_document_replace_index_atomically(database_engine, tmp_path):
    embeddings = RecordingEmbeddings()
    store = PolicyVectorStore(database_engine, embeddings, "test-model")
    store.ingest(POLICY_PATH)
    changed = tmp_path / POLICY_PATH.name
    changed.write_bytes(POLICY_PATH.read_bytes() + b"\n%Changed metadata\n")
    assert store.ingest(changed)["status"] == "indexed"
    assert PolicyVectorStore(database_engine, embeddings, "another-model").ingest(changed)["status"] == "indexed"
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM policy_documents")) == 1
        assert connection.scalar(text("SELECT count(*) FROM policy_chunks")) == 25
    assert store.search(query="Opening hours")["status"] == "not_indexed"


def test_late_write_failure_preserves_previous_index(database_engine, tmp_path):
    store = PolicyVectorStore(database_engine, RecordingEmbeddings(), "test-model")
    store.ingest(POLICY_PATH)
    with database_engine.begin() as connection:
        connection.exec_driver_sql("""CREATE FUNCTION reject_policy() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Simulated write failure'; END; $$;""")
        connection.exec_driver_sql("CREATE TRIGGER reject_policy BEFORE INSERT ON policy_chunks FOR EACH ROW EXECUTE FUNCTION reject_policy()")
    changed = tmp_path / POLICY_PATH.name
    changed.write_bytes(POLICY_PATH.read_bytes() + b"\n%Changed metadata\n")
    with pytest.raises(PolicyError, match="no changes committed"):
        store.ingest(changed)
    with database_engine.connect() as connection:
        assert connection.scalar(text("SELECT file_hash FROM policy_documents")) == sha256(POLICY_PATH.read_bytes()).hexdigest()
        assert connection.scalar(text("SELECT count(*) FROM policy_chunks")) == 25
