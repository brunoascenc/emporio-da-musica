# Sequential roadmap

## Progress rules

Complete one stage at a time: implement, validate, update documentation, and report the result. Stop for the owner's review before the next stage. Do not commit or push without an explicit request. Preserve the existing Git history.

## Stages

| Stage | Status | Deliverable | Review criteria |
| --- | --- | --- | --- |
| 1. Documentation foundation | Complete | README, architecture, roadmap, backend/frontend scaffolding, and `.gitignore` | Alignment with agreed decisions; no premature implementation |
| 2. Local infrastructure | Complete | FastAPI, settings, dependencies, backend Dockerfile, and Compose with PostgreSQL/pgvector | Nine automated tests pass, both containers are healthy, and the live health endpoint confirms PostgreSQL and pgvector |
| 3. Tabular ingestion | Complete | Alembic migration, six tables, validated CSV snapshots, and transactional upsert CLI | 26 tests pass, including isolated PostgreSQL tests for types, relationships, repeated imports, updates, and rollback |
| 4. SQL tools | Complete | Read-only catalog, price, promotion, and protected order services with LangChain tool adapters | Validated filters, bounded results, exact prices, active promotions, and order matching by number and email |
| 5. Vector retrieval | Complete | Section-aware PDF ingestion, atomic pgvector indexing, OpenAI embeddings adapter, and referenced policy search | 62 automated tests pass; authorized live indexing, unchanged reimport, and four retrieval checks succeed |
| 6. Agent | Pending | ReAct, persona, and tool integration | Simple and combined queries, limits, and error handling |
| 7. Chat and history | Pending | Chat endpoints, sessions, and persistence | Conversations survive restarts and stay isolated by session |
| 8. Interface | Pending | React/TypeScript frontend using FDD, with a `chat` feature, integrated through Compose | Send, receive, restore, and start conversations; show sources and errors; respect feature public APIs and shared-code boundaries |
| 9. Submission | Pending | Evaluation, five real conversations, CI, and final README | Clean-clone execution, passing checks, and documented limitations |

Tests will accompany features. Stage 9 consolidates evaluation rather than postponing essential validation. Backend work stays under `backend/`; frontend work stays under `frontend/`.

## Stage 2 validation

- Nine automated tests pass: settings precedence, required password, port validation, password handling, healthy database, missing pgvector, and database failure without leaking connection details.
- Docker Compose configuration passes `config --quiet` with the local environment file.
- Live Docker verification passes: both images build and both containers become healthy. `GET /api/health` returns HTTP 200 with `{"status":"healthy","database":"up","pgvector":true}`.
- The earlier Docker engine startup issue cleared after starting Docker Desktop again. An existing host service occupies port 5432, so this project publishes PostgreSQL on configurable host port 5433 while retaining container port 5432.
- No ingestion, model integration, chat, or frontend behavior has been implemented in this stage.

## Stage 3 validation

- The source CSVs are copied unchanged into `backend/data/`.
- Alembic creates the six tables with explicit types, keys, foreign keys, indexes, and checks. Applying the migration twice succeeds.
- Both initial and repeated imports succeed in Docker, processing 9 categories, 50 customers, 65 products, 20 orders, 22 order items, and 25 promotions.
- The complete suite passes 26 tests, including PostgreSQL tests that use temporary isolated schemas. A simulated failure at the final promotions table verifies that changes to earlier tables are rolled back.
- Invalid fields, headers, duplicate keys, missing files, and broken references are rejected without exposing source values. Existing records are updated on repeat import without duplicates.
- No retrieval tools, policy embeddings, model integration, chat, or frontend behavior is implemented in this stage.

## Stage 4 validation

- The complete suite passes 45 tests, including live PostgreSQL integration checks. The rebuilt Docker backend remains healthy, and all four tools were invoked successfully against the project database without model calls.
- Four tools are available: `list_categories`, `search_products`, `get_product`, and `get_order`. No new HTTP endpoints or model calls are introduced.
- Unit tests cover argument validation before database access, read-only transactions, parameter binding, wildcard escaping, decimal rounding, and sanitized errors.
- PostgreSQL tests cover accent-insensitive category/budget search, stock and lifecycle filtering, inactive promotions, selecting one active discount, discounted-price budget boundaries, result limits, literal SQL-like input, and order lookup with matching or incorrect email.
- Existing migration and ingestion tests continue to cover isolated schemas, data types, upserts, and rollback. All database tests leave operational data untouched.
- Policy retrieval, payment-policy application, agent orchestration, chat, and frontend implementation remain for later stages.

## Stage 5 validation

- The original policy PDF is copied unchanged into `backend/data/`. Layout extraction produces 25 referenced chunks with page ranges, numbered sections, parent context, and payment-table text.
- The complete suite passes 62 tests, including local PostgreSQL tests for vector storage, exact retrieval, references, unchanged imports without embedding calls, model changes, and preservation of the previous index on provider or database failure.
- The vector-table migration is applied to the project database, and Docker containers remain healthy. Automated tests use mocked OpenAI responses or deterministic local vectors in isolated schemas; they do not validate real embedding relevance.
- After explicit authorization to send the manual text to OpenAI, live indexing stored 25 chunks using the configured embedding model. A repeat import reported `status=unchanged` and `embedded_chunks=0`.
- Four live retrieval checks returned the expected primary sections: opening hours (`2`), payments (`3.1` and `3`), online returns (`4.1`), and legal warranty (`8.1`). All returned passages include valid source, document hash, section, and page references. This is a smoke evaluation, not a comprehensive retrieval benchmark.
- Agent orchestration, payment-policy application, conversation APIs, and frontend implementation remain for later stages.
