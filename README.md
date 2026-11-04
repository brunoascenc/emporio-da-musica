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

The six supplied CSV files are included in `backend/data/` without modifying their contents. The original materials remain in the repository's parent directory. The policy PDF will be added during the policy retrieval stage.

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
│   ├── data/
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

The backend infrastructure, operational schema, CSV ingestion, and structured database tools are implemented. Agent orchestration, policy retrieval, chat, and frontend features remain planned.

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

## Migrations and CSV ingestion

After starting the containers, run these explicit commands from the repository root:

```powershell
docker compose --env-file backend/.env exec -T backend python -m alembic upgrade head
docker compose --env-file backend/.env exec -T backend python -m scripts.import_data
```

The API does not run migrations or import data automatically. The container image includes the six CSV files from `backend/data/`; rebuild the backend image after changing those files. For host execution, use the equivalent commands from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.import_data
```

The importer defaults to `backend/data/` independently of the working directory. Its optional `--data-dir` argument accepts another directory containing all six CSV files with the same column names. All files are validated before database writes: expected headers, typed fields, primary key uniqueness, and references to rows in the supplied snapshot. Invalid input reports the filename, record, and field without printing customer data.

All six tables are imported in a single transaction. Existing primary keys are updated, new keys are inserted, and database failures roll back the entire import. Repeating an import does not create duplicates. Rows absent from the supplied files are retained; this command is not a destructive snapshot replacement. References must resolve within the supplied files, even if additional rows already exist in the database.

On success, the command prints a JSON report with `rows_processed` per table. These are processed source records, not counts of newly inserted rows. Failures exit with a nonzero status. The supplied snapshot contains:

| Table | Rows |
| --- | ---: |
| `categories` | 9 |
| `customers` | 50 |
| `products` | 65 |
| `orders` | 20 |
| `order_items` | 22 |
| `promotions` | 25 |

Money is stored as `NUMERIC`, dates as `DATE`, product specifications as `JSONB`, and promotion activation as a boolean. Empty optional order fields become SQL `NULL`. Order items use the composite primary key `(order_id, product_id)`.

## PostgreSQL integration tests

The default test command skips live database tests. With the project database running, run the complete suite from `backend/`:

```powershell
$env:RUN_DB_TESTS = '1'
try {
    .\.venv\Scripts\python.exe -m pytest -q
} finally {
    Remove-Item Env:RUN_DB_TESTS
}
```

Integration tests create and remove uniquely named temporary schemas in the configured database, leaving operational tables untouched. They verify migration repeatability, typed data, relationships, repeated imports, updates, and rollback after a late database failure. The database user needs permission to create schemas. No OpenAI calls are made.

## Operational agent tools

`backend/src/langchain_layer/tools/` exposes `build_store_tools(engine)`, which builds four LangChain structured tools with validated input schemas. The SQL and result formatting live in `backend/src/services/store_queries.py`. No model or OpenAI key is required to invoke these tools.

| Tool | Inputs | Behavior |
| --- | --- | --- |
| `list_categories` | None | Return category IDs, names, and descriptions, bounded to 100 categories |
| `search_products` | Optional `query`, `category_id`, `max_price_brl`, `only_available`, `limit` | Search name, description, and category; default to available products and five results, with a maximum of 20 |
| `get_product` | `product_id` | Return current price, selected promotion, specifications, stock, and lifecycle status |
| `get_order` | `order_id` and `email` | Return matching order status, dates, total, payment method, tracking code, and up to 50 items |

Example from a Python session started in `backend/`, after migrating and importing the database:

```python
from src.core.config import Settings
from src.core.database import create_database_engine
from src.langchain_layer.tools import build_store_tools

engine = create_database_engine(Settings())
try:
    tools = {tool.name: tool for tool in build_store_tools(engine)}
    result = tools["search_products"].invoke({
        "query": "violao",
        "max_price_brl": "1000.00",
        "limit": 5,
    })
    print(result)
finally:
    engine.dispose()
```

Search ignores case and common Portuguese accents. User text is a literal substring, including SQL wildcard characters. Results are ordered by current unit price, then product ID; `has_more` indicates when the search can be refined. Availability requires `status=active` and positive stock. Set `only_available=false` to inspect unavailable or discontinued products; their `available` flag remains false.

Prices are BRL decimal strings with two decimal places. The original price and promotion details are returned together. Only positive, active promotions apply. If multiple promotions are active for the same product, select the largest discount, breaking ties by promotion ID; discounts are never stacked. Budget filtering uses exact PostgreSQL numeric arithmetic, and returned prices use Python `Decimal` with half-up rounding. Payment-specific discounts and installment rules require policy retrieval and are deferred to the agent integration stage.

Order email comparison ignores surrounding whitespace and case. A missing order and an incorrect email produce the same `not_found` result. Order responses omit customer identity, email, phone, and internal notes, and do not infer receipt dates or historical item prices from current catalog values. `items_truncated` indicates whether more than 50 items exist.

All lookups run in read-only transactions using fixed SQL and bound parameters. No arbitrary SQL or customer-listing tool is exposed. Invalid arguments are rejected before database access; database failures return a sanitized tool error. There are no additional HTTP endpoints in this stage.

## Prototype boundaries

- Queries data and explains policies; does not execute purchases, cancellations, refunds, or real handoffs.
- Operational data is a snapshot of the supplied materials without external store integrations.
- Order lookup requires the order number and matching email. This demonstration check does not replace production authentication.
- Local execution only; public deployment is outside this version. The submission repository must be public.
- The external submission deadline must be supplied before establishing the final repository freeze.
