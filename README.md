# Empório da Música

## Planned architecture

```text
Customer → React chat → FastAPI → ReAct agent (LangChain)
                                  ├─ SQL tools → PostgreSQL
                                  └─ Policy retrieval → pgvector
                         Session history → PostgreSQL
```

React is the frontend library; ReAct is the agent's reasoning and tool-use loop in the backend.

- **Backend:** Python, FastAPI, and Pydantic Settings.
- **Agent:** LangChain with dedicated data lookup and policy retrieval tools.
- **Database:** PostgreSQL, SQLAlchemy, and Psycopg3, using parameterized queries.
- **Policies:** pgvector within PostgreSQL, with page and section references.
- **Frontend:** React, TypeScript, and Vite, organized with Feature-Driven Development (FDD).
- **Runtime:** Docker Compose for the local database, backend, and frontend.
- **History:** PostgreSQL sessions identified by UUID.
- **LLM:** gpt-6-luna.

See [architecture decisions](docs/architecture.md) and the [sequential roadmap](docs/roadmap.md).

## Data sources

The supplied materials currently reside in the repository's parent directory. They will be copied into the project during the ingestion stages.

| Source | Planned destination |
| --- | --- |
| `categories.csv` | `categories` table |
| `customers.csv` | `customers` table |
| `products.csv` | `products` table |
| `orders.csv` | `orders` table |
| `order_items.csv` | `order_items` table |
| `promotions.csv` | `promotions` table |
| `políticas_da_loja.pdf` | Policy chunks and embeddings in pgvector |

The tabular sources are CSV files. The challenge brief is a development reference and will not be embedded as store knowledge. Original source filenames and the store's proper name are preserved.

## Project structure

```text
emporio-da-musica/
├── README.md
├── .gitignore
├── docs/
│   ├── architecture.md
│   └── roadmap.md
├── backend/
│   ├── src/
│   │   ├── core/
│   │   ├── api/
│   │   ├── services/
│   │   └── langchain_layer/tools/
│   ├── migrations/
│   ├── scripts/
│   └── tests/
└── frontend/
    └── src/
        ├── app/
        ├── components/
        ├── features/
        │   └── chat/
        ├── hooks/
        ├── lib/
        ├── types/
        └── utils/
```

All backend implementation, dependencies, configuration examples, Dockerfile, migrations, ingestion scripts, and tests belong under `backend/`. Frontend implementation and its build configuration belong under `frontend/`. Shared documentation and orchestration belong at the repository root.

The backend infrastructure is implemented. Agent, ingestion, chat, and frontend features remain planned.

## Run the local infrastructure

Prerequisite: Docker Desktop with the Linux container engine running and Docker Compose available. Run these PowerShell commands from the repository root:

```powershell
Copy-Item backend/.env.example backend/.env
docker compose --env-file backend/.env up --build -d --wait
Invoke-RestMethod http://localhost:8000/api/health
```

Copy the environment example only on first setup; preserve your existing `.env` on subsequent runs. The example credentials are for local development. No OpenAI key is required at this stage.

The health response is `{"status":"healthy","database":"up","pgvector":true}`. An unreachable database or missing vector extension returns HTTP 503. Interactive API documentation is available at <http://localhost:8000/docs>.

Only PostgreSQL and the backend run at this stage. Both published ports are bound to localhost (`5433` and `8000`). The database host port is configurable through `POSTGRES_PORT` in `backend/.env`; the container always uses port `5432`. PostgreSQL data is stored in a named volume. The initialization script in `backend/scripts/initdb/` enables pgvector when creating a new database volume; it does not run again on an existing volume. To enable the extension on an existing project database, run:

```powershell
docker compose --env-file backend/.env exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS vector;"'
```

Operational commands:

```powershell
docker compose --env-file backend/.env ps
docker compose --env-file backend/.env logs backend db
docker compose --env-file backend/.env down
```

`down` preserves the database volume. Changing database credentials in `.env` does not update an existing database automatically.

## Backend development and tests

Use Python 3.12. From the repository root, after creating `backend/.env`:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

The tests simulate database responses and do not require Docker or OpenAI. To run the backend directly against the containerized database, start only the database from the repository root:

```powershell
docker compose --env-file backend/.env up -d db --wait
cd backend
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload
```

Do not run the containerized backend and host backend simultaneously on port 8000. Host execution uses `POSTGRES_HOST=localhost` from `backend/.env`; Compose overrides it to `db`. Settings load that file independently of the working directory, and process environment variables take precedence. Startup validates configuration, while the health endpoint verifies the live database and extension. The connection pool is disposed on shutdown.

## Prototype boundaries

- Queries data and explains policies; does not execute purchases, cancellations, refunds, or real handoffs.
- Operational data is a snapshot of the supplied materials without external store integrations.
- Order lookup requires the order number and matching email. This demonstration check does not replace production authentication.
- Local execution only; public deployment is outside this version. The submission repository must be public.
- The external submission deadline must be supplied before establishing the final repository freeze.
