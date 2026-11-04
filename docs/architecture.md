# Architecture and decisions

Status: backend infrastructure, operational migrations, CSV ingestion, structured database tools, and policy retrieval are implemented and validated against PostgreSQL. Authorized live OpenAI indexing and four retrieval checks also pass. Agent orchestration, chat, and frontend features remain planned.

## Responsibilities

All paths below are relative to `backend/` unless otherwise stated. They describe planned implementation files.

| Layer | Responsibility |
| --- | --- |
| `src/main.py` | Create and configure the FastAPI application |
| `src/core/config.py` | Parse and validate environment variables with Pydantic Settings |
| `src/core/database.py` | Manage the database engine, connections, and sessions |
| `src/core/llm.py` | Initialize configurable OpenAI models |
| `src/api/schemas.py` | Validate HTTP request and response contracts |
| `src/api/` | Declare endpoints and assemble the API router |
| `src/services/workflow.py` | Coordinate history, agent execution, and API results |
| `src/langchain_layer/agent.py` | Define the ReAct loop and register tools |
| `src/langchain_layer/prompts.py` | Define persona, scope, and source-use instructions |
| `src/langchain_layer/tools/` | Query products and orders with parameterized SQL and retrieve policies |
| `src/langchain_layer/vectorstore.py` | Integrate embeddings with pgvector |
| `scripts/` and `migrations/` | Run explicit ingestion and evolve the database |
| Repository-level `frontend/` | Implement the React conversation interface |

Backend dependency manifests, Dockerfile, environment examples, and tests stay in `backend/`. Frontend equivalents stay in `frontend/`. Shared Compose configuration and documentation stay at the repository root. API handlers will not contain prompts or SQL; the frontend will not hold OpenAI credentials or connect directly to the database.

## Frontend architecture

The frontend uses Feature-Driven Development (FDD). Business behavior belongs inside feature domains; shared folders contain only code used across features. All paths in this section are relative to `frontend/` and describe the planned structure.

```text
src/
├── app/
│   ├── providers.tsx     # Global context providers
│   ├── routes.tsx        # Top-level route aggregation
│   └── store.ts          # Central store configuration, when needed
├── components/           # Generic shared UI: buttons, inputs, modals
├── features/
│   └── chat/             # Conversation domain
├── hooks/                # Cross-feature hooks
├── lib/                  # Third-party library and API client configuration
├── types/                # Cross-feature TypeScript definitions
└── utils/                # Pure cross-feature helpers
```

`app/` owns application entry points, configuration, routing, and provider composition. Providers and a central store are added only when required; this structure does not require introducing authentication, Redux, or Zustand upfront.

The initial business feature is `chat`, which owns sending messages, restoring conversation history, session state, and displaying responses and policy references:

```text
features/chat/
├── api/                  # Chat and conversation history requests
├── components/           # Chat-specific UI
├── hooks/                # Conversation state and interaction logic
├── types/                # Chat request, response, and state types
├── index.ts              # Public API for consumers outside the feature
└── README.md             # Optional explanation of feature boundaries
```

- External consumers import a feature through its `index.ts`; expose only what they need, keeping implementation details private.
- Feature-specific requests, components, hooks, and types stay inside their feature. Shared folders must not import business features.
- `app/` composes features. Avoid direct imports into another feature's internal folders and circular dependencies.
- Shared API client configuration belongs in `lib/`; endpoint-specific request functions belong in the relevant feature's `api/` directory.
- Add domains such as `auth`, `dashboard`, or `products` only when required by product scope. They illustrate the pattern and are not planned screens for this chat prototype.
- Create files alongside working behavior rather than adding empty providers, stores, or routes in advance.

## Operational data

Each CSV maps to a table named after its filename without the extension. Schemas will explicitly reflect headers and contents, with validated keys and relationships.

The initial Alembic migration creates all six tables. Source identifiers are externally assigned integer primary keys, with `(order_id, product_id)` as the composite key for `order_items`. Foreign keys connect products to categories, orders to customers, items to orders and products, and promotions to products. Foreign key lookup columns are indexed. Database constraints enforce nonnegative money and stock, positive quantities, valid statuses, object-shaped specifications, and discount percentages between 0 and 100.

- Money uses decimal types rather than floating-point arithmetic.
- Dates use appropriate date types; `products.specs` uses JSONB.
- Imports are transactional and repeatable without duplication. Inconsistencies produce diagnostics rather than silent corrections.
- Product and order tools use parameterized queries with bounded results. The agent has no arbitrary SQL tool or general customer listing tool.
- The backend validates the order number and matching email before returning information. Logs must not record these personal identifiers.

CSV parsing and validation live in `backend/src/services/ingestion.py` and `ingestion_schemas.py`; `backend/scripts/import_data.py` exposes the explicit CLI command. The six original CSVs are included under `backend/data/`. All files are validated before writes, including duplicate keys and references within the supplied snapshot. A single transaction performs PostgreSQL upserts in dependency order. Existing keys are updated, absent keys are retained, and any database failure rolls back every table. Diagnostics identify the file, record, and invalid fields without exposing field values. The JSON success report counts processed source rows rather than new inserts.

## Operational lookup tools

`src/services/store_queries.py` owns fixed parameterized SQL and structured results. `src/services/store_schemas.py` validates lookup arguments. `src/langchain_layer/tools/` adapts these services into LangChain structured tools through `build_store_tools(engine)` without initializing an LLM.

- `list_categories` returns up to 100 category descriptions and IDs.
- `search_products` filters by literal name/description/category substring, category ID, discounted unit-price budget, and availability. Search ignores case and common Portuguese accents. Return five products by default, at most 20, plus `has_more`; sort by current price and product ID.
- `get_product` returns price, active promotion, availability, lifecycle status, and specifications by product ID. Unavailable products can be inspected without implying they can be purchased.
- `get_order` requires both order number and matching email. Return only the matched order and up to 50 items, with `items_truncated`. Email comparison ignores case and surrounding whitespace. Missing order and mismatched email share the same not-found result; customer identifiers and internal notes are omitted.

Queries run inside read-only transactions. Only predefined statements and bound parameters are exposed; errors do not include SQL, database details, or customer values. Input validation occurs before database access.

When several positive promotions are active for a product, select the highest discount, breaking ties by promotion ID. Inactive discounts are ignored and promotions are not stacked. Return original price, selected promotion, and current unit price as decimal strings. Budget comparison and price ordering use exact PostgreSQL numeric arithmetic with the same half-up cent rounding used by Python `Decimal` when formatting responses. PIX and installment conditions remain deferred until policy retrieval and agent orchestration are available.

## Policy retrieval

Only the store manual is selected by the default ingestion command. `src/services/policy_pdf.py` extracts numbered sections using PDF layout text, preserving parent headings, table rows, page ranges, and source hashes. The supplied manual produces 25 chunks, bounded to 3,000 characters with 300-character overlap for long sections. Running headers and page footers are excluded; scanned PDFs require future OCR support.

The `policy_documents` and `policy_chunks` tables store one current revision per filename with `public.vector(1536)` embeddings. `src/core/embeddings.py` implements the LangChain embeddings interface using the OpenAI SDK, with batches of at most 32 chunks, a 30-second request timeout, and two retries. The configured model defaults to `text-embedding-3-small`. Both supported embedding models explicitly request 1,536 dimensions to match the schema.

`src/langchain_layer/vectorstore.py` checks the file hash, extraction pipeline identifier, model, dimensions, and stored chunk count before any embedding call. It serializes same-source imports with a transaction advisory lock and replaces documents and chunks in a single transaction after successful extraction and embedding. Failures preserve the previous index, but provider charges already incurred cannot be rolled back. A different filename creates another source. No embedding runs automatically on API startup.

Exact cosine search returns four primary matches by default, with an upper limit of eight. Adjacent chunks from the same top-level policy topic can add at most two passages per primary hit, without duplicates. Search uses a read-only repeatable snapshot and returns source, document hash, page range, section, content, distance, and match type. No approximate vector index is needed for this small corpus. An incompatible or missing index is reported before embedding the query.

`src/langchain_layer/tools/policies.py` exposes the `search_policies` structured tool through `build_policy_tool(store)`. Retrieved text is domain evidence, not system instructions, and similarity does not establish applicability. Agent orchestration and responses based on these passages remain deferred to stage 6.

## Agent behavior

- Use an informal, professional tone suited to a musical instrument store. Match the customer's language; project documentation and implementation text use English.
- Query the database before asserting prices, availability, promotions, or order status.
- Retrieve policies for opening hours, payments, exchanges, returns, and warranties.
- Combine tools when a question requires both operational data and policies.
- Perform financial calculations in Python using `Decimal`; do not stack PIX discounts with promotions.
- Ask for missing or ambiguous information and politely redirect out-of-scope questions.
- Do not claim to cancel orders, register complaints, or perform other actions without a corresponding integration.
- Bound context and tool iterations; handle dependency failures without inventing answers.

## Planned public contracts

| Method and route | Minimum contract |
| --- | --- |
| `GET /api/health` | Check application and database availability without a paid model call |
| `POST /api/chat` | Accept a message and optional session UUID; return the session UUID, answer, and references |
| `GET /api/conversations/{session_id}` | Return the ordered history of an existing session |

The backend generates UUIDs for new sessions and persists history in PostgreSQL. The browser stores the session identifier to restore conversations. The first version returns complete responses without streaming. No additional `/query` endpoint is planned without a functional need.

## Source ambiguities and limitations

- Orders include estimated delivery dates, not actual receipt dates. Ask for the receipt date and purchase channel when needed to assess returns.
- The manual lists different phone numbers. Prefer the channel-specific section; disclose unresolved conflicts and recommend confirmation with the store team.
- Specific installment rules take precedence over the general summary; flag unresolved conflicts.
- Active promotions come from the database. The manual's campaign calendar does not prove that an offer is active.
- Do not assume holidays, product-specific warranty coverage, calculated shipping quotes, or live tracking events without supporting data.
- Store opening hours use `America/Campo_Grande`.

## Configuration and operation

Docker Compose currently defines PostgreSQL with pgvector and the FastAPI backend, using a persistent database volume. The frontend service will be added with the interface implementation. A first-volume initialization script enables the vector extension; application startup does not create tables or ingest data. Alembic migrations and CSV ingestion are explicit documented commands. Normal startup must not repeat ingestion or embedding calls.

The implemented health endpoint checks PostgreSQL connectivity and whether the vector extension is installed. It returns HTTP 200 for healthy dependencies and HTTP 503 for connection failures or a missing extension, without returning database exception details. Settings are validated on startup, the SQLAlchemy pool uses connection pre-ping and bounded timeouts, and shutdown disposes the engine. OpenAI key configuration is optional for startup and operational SQL tools and required only when policy embeddings are requested. Health does not call OpenAI or assert that a policy index exists.

Only configuration examples are versioned; actual environment files and credentials are excluded. Dependency versions will be pinned as components are implemented. Automated tests use simulated OpenAI responses; live evaluation is separate.
