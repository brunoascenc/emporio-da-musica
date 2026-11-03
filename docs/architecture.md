# Architecture and decisions

Status: approved design for sequential implementation; features are not implemented yet.

## Responsibilities

All paths below are relative to `backend/` unless otherwise stated. They describe planned implementation files.

| Layer | Responsibility |
| --- | --- |
| `src/main.py` | Create and configure the FastAPI application |
| `src/core/config.py` | Parse and validate environment variables with Pydantic Settings |
| `src/core/database.py` | Manage the database engine, connections, and sessions |
| `src/core/llm.py` | Initialize configurable OpenAI models |
| `src/api/schemas.py` | Validate HTTP request and response contracts |
| `src/api/v1/` | Declare endpoints and assemble the versioned router |
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

- Money uses decimal types rather than floating-point arithmetic.
- Dates use appropriate date types; `products.specs` uses JSONB.
- Imports are transactional and repeatable without duplication. Inconsistencies produce diagnostics rather than silent corrections.
- Product and order tools use parameterized queries with bounded results. The agent has no arbitrary SQL tool or general customer listing tool.
- The backend validates the order number and matching email before returning information. Logs must not record these personal identifiers.

## Policy retrieval

Only the store manual will be embedded. Ingestion preserves sections, table context, pages, source names, and content hashes. Repeating ingestion without changes must not trigger additional paid embedding calls.

Retrieval initially returns four similar chunks and may include adjacent sections to complete a rule. Responses expose references to the sources used. Retrieved content is domain evidence, not instructions that can override system behavior.

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
| `GET /api/v1/health` | Check application and database availability without a paid model call |
| `POST /api/v1/chat` | Accept a message and optional session UUID; return the session UUID, answer, and references |
| `GET /api/v1/conversations/{session_id}` | Return the ordered history of an existing session |

The backend generates UUIDs for new sessions and persists history in PostgreSQL. The browser stores the session identifier to restore conversations. The first version returns complete responses without streaming. No additional `/query` endpoint is planned without a functional need.

## Source ambiguities and limitations

- Orders include estimated delivery dates, not actual receipt dates. Ask for the receipt date and purchase channel when needed to assess returns.
- The manual lists different phone numbers. Prefer the channel-specific section; disclose unresolved conflicts and recommend confirmation with the store team.
- Specific installment rules take precedence over the general summary; flag unresolved conflicts.
- Active promotions come from the database. The manual's campaign calendar does not prove that an offer is active.
- Do not assume holidays, product-specific warranty coverage, calculated shipping quotes, or live tracking events without supporting data.
- Store opening hours use `America/Campo_Grande`.

## Configuration and operation

Docker Compose will run PostgreSQL with pgvector, the backend, and the frontend, using a persistent database volume. Migrations and ingestion are explicit documented commands. Normal startup must not repeat ingestion or embedding calls.

Only configuration examples are versioned; actual environment files and credentials are excluded. Dependency versions will be pinned as components are implemented. Automated tests use simulated OpenAI responses; live evaluation is separate.
