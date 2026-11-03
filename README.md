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
│   │   ├── api/v1/
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

Implementation directories currently contain placeholders only. Dependency manifests, environment examples, Dockerfiles, and entry points will be added alongside their implementation.

## Prototype boundaries

- Queries data and explains policies; does not execute purchases, cancellations, refunds, or real handoffs.
- Operational data is a snapshot of the supplied materials without external store integrations.
- Order lookup requires the order number and matching email. This demonstration check does not replace production authentication.
- Local execution only; public deployment is outside this version. The submission repository must be public.
- The external submission deadline must be supplied before establishing the final repository freeze.
