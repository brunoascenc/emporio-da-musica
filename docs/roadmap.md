# Sequential roadmap

## Progress rules

Complete one stage at a time: implement, validate, update documentation, and report the result. Stop for the owner's review before the next stage. Do not commit or push without an explicit request. Preserve the existing Git history.

## Stages

| Stage | Status | Deliverable | Review criteria |
| --- | --- | --- | --- |
| 1. Documentation foundation | Complete | README, architecture, roadmap, backend/frontend scaffolding, and `.gitignore` | Alignment with agreed decisions; no premature implementation |
| 2. Local infrastructure | Complete | FastAPI, settings, dependencies, backend Dockerfile, and Compose with PostgreSQL/pgvector | Nine automated tests pass, both containers are healthy, and the live health endpoint confirms PostgreSQL and pgvector |
| 3. Tabular ingestion | Pending | Migrations, six tables, and CSV imports | Correct types, relationships, counts, transactions, and repeatable imports |
| 4. SQL tools | Pending | Product, price, promotion, and order lookups | Correct queries and order access checked by number and email |
| 5. Vector retrieval | Pending | PDF ingestion, embeddings, and referenced policy search | Relevant sections retrieved; unchanged sources do not trigger new embeddings |
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
