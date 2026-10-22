# ADR 001: explicit durable workflow

Status: accepted.

Use a small explicit state machine in PostgreSQL, shared by API and worker. Job leases and checkpoints make recovery inspectable without introducing Redis or a workflow platform. External idempotency receipts close the gap between an HTTP mutation and a product checkpoint. The cost is maintaining lease/recovery tests; transactions alone cannot guarantee exactly-once effects across services.

# ADR 002: one trusted tool registry

Status: accepted.

Direct and MCP transports invoke the same validated registry. stdio stays local and does not expose a public MCP endpoint requiring OAuth. Signed context binds each subprocess to one actor, tenant, and run. Approval and execution are never exposed as model tools.

# ADR 003: SPA and isolated demo services

Status: accepted.

Use React/Vite and a FastAPI-served production bundle. This work surface does not require SSR. Keep the synthetic business API and its database separate so reads, effects, ambiguous outcomes, and verification are actual integration behavior.

# ADR 004: free live models, explicit offline mode

Status: accepted.

Use OpenRouter over its documented HTTP chat/tool interface. Only a verified zero-price model with tool support, or the provider's free router, may be selected by the development configuration. No paid fallback. Live and deterministic runs carry distinct labels, and live failures remain visible. Persist returned model and reported usage; do not invent a dollar estimate when absent.
