"""Store one current policy revision per source and its referenced vectors."""

from alembic import op

revision = "0002_policy_vectors"
down_revision = "0001_operational_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
    op.execute("""
        CREATE TABLE policy_documents (
            source_name text PRIMARY KEY,
            file_hash varchar(64) NOT NULL,
            pipeline_id text NOT NULL,
            embedding_model text NOT NULL,
            dimensions integer NOT NULL CHECK (dimensions = 1536),
            chunk_count integer NOT NULL CHECK (chunk_count > 0),
            indexed_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE policy_chunks (
            source_name text NOT NULL REFERENCES policy_documents(source_name) ON DELETE CASCADE,
            chunk_index integer NOT NULL CHECK (chunk_index >= 0),
            section text NOT NULL,
            section_title text NOT NULL,
            page_start integer NOT NULL CHECK (page_start > 0),
            page_end integer NOT NULL CHECK (page_end >= page_start),
            content text NOT NULL,
            embedding public.vector(1536) NOT NULL,
            PRIMARY KEY (source_name, chunk_index)
        )
    """)


def downgrade():
    op.drop_table("policy_chunks")
    op.drop_table("policy_documents")
    # The shared vector extension is also used outside these tables.
