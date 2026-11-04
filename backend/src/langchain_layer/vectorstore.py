"""Exact pgvector retrieval for a small, section-aware policy corpus."""

from dataclasses import asdict
import json
import math
from pathlib import Path

from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from src.core.embeddings import DIMENSIONS
from src.services.policy_pdf import PIPELINE_ID, PolicyError, document_hash, extract_chunks, read_policy


class PolicySearch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    query: str = Field(min_length=2, max_length=1000)
    limit: int = Field(default=4, ge=1, le=8)
    include_neighbors: bool = True


def vector_parameter(vector) -> str:
    try:
        valid = len(vector) == DIMENSIONS and all(math.isfinite(value) for value in vector) and any(vector)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise PolicyError("The embedding provider returned an invalid 1536-dimensional vector.")
    return json.dumps(vector, allow_nan=False)


class PolicyVectorStore:
    def __init__(self, engine: Engine, embeddings: Embeddings, model: str):
        self.engine, self.embeddings, self.model = engine, embeddings, model

    def ingest(self, path: Path) -> dict:
        raw = read_policy(path)
        fingerprint = document_hash(raw)
        parameters = {"source_name": path.name, "file_hash": fingerprint, "pipeline_id": PIPELINE_ID, "model": self.model, "dimensions": DIMENSIONS}
        try:
            with self.engine.begin() as connection:
                connection.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:source_name, 0))"), parameters)
                existing = connection.execute(text("""
                    SELECT d.*, (SELECT count(*) FROM policy_chunks c WHERE c.source_name=d.source_name) AS actual_count
                    FROM policy_documents d WHERE source_name=:source_name
                """), parameters).mappings().one_or_none()
                if existing and all(existing[key] == parameters[key] for key in ("file_hash", "pipeline_id", "dimensions")) and existing["embedding_model"] == self.model and existing["actual_count"] == existing["chunk_count"]:
                    return {"status": "unchanged", "source": path.name, "chunks": existing["chunk_count"], "embedded_chunks": 0}
                chunks = extract_chunks(raw)
                vectors = self.embeddings.embed_documents([chunk.content for chunk in chunks])
                if len(vectors) != len(chunks):
                    raise PolicyError("The embedding provider returned an incomplete response.")
                vector_strings = [vector_parameter(vector) for vector in vectors]
                connection.execute(text("""
                    INSERT INTO policy_documents (source_name, file_hash, pipeline_id, embedding_model, dimensions, chunk_count)
                    VALUES (:source_name,:file_hash,:pipeline_id,:model,:dimensions,:chunk_count)
                    ON CONFLICT (source_name) DO UPDATE SET
                        file_hash=excluded.file_hash, pipeline_id=excluded.pipeline_id,
                        embedding_model=excluded.embedding_model, dimensions=excluded.dimensions,
                        chunk_count=excluded.chunk_count, indexed_at=now()
                """), {**parameters, "chunk_count": len(chunks)})
                connection.execute(text("DELETE FROM policy_chunks WHERE source_name=:source_name"), parameters)
                connection.execute(text("""
                    INSERT INTO policy_chunks (source_name,chunk_index,section,section_title,page_start,page_end,content,embedding)
                    VALUES (:source_name,:chunk_index,:section,:section_title,:page_start,:page_end,:content,CAST(:embedding AS public.vector))
                """), [{**asdict(chunk), "source_name": path.name, "embedding": vector} for chunk, vector in zip(chunks, vector_strings)])
        except SQLAlchemyError:
            raise PolicyError("Policy indexing failed; no changes committed. Check the database and apply migrations.") from None
        return {"status": "indexed", "source": path.name, "chunks": len(chunks), "embedded_chunks": len(chunks)}

    def search(self, **arguments) -> dict:
        request = PolicySearch(**arguments)
        try:
            with self.engine.begin() as connection:
                connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                available = connection.scalar(text("SELECT count(*) FROM policy_documents WHERE embedding_model=:model AND dimensions=:dimensions"), {"model": self.model, "dimensions": DIMENSIONS})
                if not available:
                    return {"status": "not_indexed", "message": "No policies are indexed for the configured embedding model.", "passages": []}
                vector = vector_parameter(self.embeddings.embed_query(request.query))
                rows = connection.execute(text("""
                    SELECT c.source_name,d.file_hash,c.chunk_index,c.section,c.section_title,c.page_start,c.page_end,c.content,
                           c.embedding OPERATOR(public.<=>) CAST(:vector AS public.vector) AS distance
                    FROM policy_chunks c JOIN policy_documents d USING(source_name)
                    WHERE d.embedding_model=:model AND d.dimensions=:dimensions
                    ORDER BY distance,c.source_name,c.chunk_index LIMIT :limit
                """), {"vector": vector, "model": self.model, "dimensions": DIMENSIONS, "limit": request.limit}).mappings().all()
                passages = {(row["source_name"], row["chunk_index"]): {**dict(row), "match_type": "similarity"} for row in rows}
                if request.include_neighbors:
                    for row in rows:
                        neighbors = connection.execute(text("""
                            SELECT source_name,chunk_index,section,section_title,page_start,page_end,content
                            FROM policy_chunks WHERE source_name=:source_name
                            AND chunk_index IN (:previous,:following)
                            AND split_part(section,'.',1)=:family ORDER BY chunk_index
                        """), {"source_name": row["source_name"], "previous": row["chunk_index"]-1, "following": row["chunk_index"]+1, "family": row["section"].split(".")[0]}).mappings().all()
                        for neighbor in neighbors:
                            key = (neighbor["source_name"], neighbor["chunk_index"])
                            passages.setdefault(key, {**dict(neighbor), "file_hash": row["file_hash"], "distance": None, "match_type": "adjacent"})
        except SQLAlchemyError:
            raise PolicyError("Policy retrieval is unavailable; check the database and migrations.") from None
        return {"status": "ok", "passages": list(passages.values()), "context_only": True}
