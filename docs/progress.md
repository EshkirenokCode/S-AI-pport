# Implementation progress

## Foundation and billing vertical

- Product, architecture, contracts, permissions, threats and testing are recorded.
- Isolated product/sandbox PostgreSQL databases and checksum-verified migrations run locally.
- The API, durable worker, seven scoped tools and real stdio MCP transport are implemented.
- The billing vertical was exercised over real HTTP: evidence → proposal → approval → one operation → a fresh Pro-access verification.
- The React workspace builds successfully and the billing investigation/approval path was exercised in the browser.
- Offline runs are explicitly labelled. The OpenRouter adapter allows only zero-price models with no paid fallback.

## Live checkpoint

The first OpenRouter free-router investigation invoked all six necessary tools and reached a grounded proposal awaiting approval. Six reported model calls cost $0. Full live completion and additional scenario validation are in progress.

## Next

Finish integration/security/recovery tests, validate the remaining workflows, measure retrieval and evaluations, and package reproducible startup and delivery materials.

## Live model and reliability

- Real OpenRouter free-router smoke runs completed billing (6 model calls), integration delivery (5), and configuration (4). All reported costs were zero. Both repairs were re-read and verified; stdio MCP was used in each investigation. Reports are under evals/reports.
- 33 backend tests pass using real PostgreSQL, separate HTTP services, and MCP subprocesses, including ambiguous-operation receipt reconciliation, role revocation, stale state, and exhausted recovery/deadline budgets.
- 36 deterministic workflow evaluation cases pass (24 development, 12 holdout); no duplicate effects. This is contract coverage, not measured LLM accuracy.
- Six browser tests passed: billing, integration, configuration, analyst role, permanent error, and mobile. Screenshots were captured from the real product.
- Docker Compose and CI are prepared; container CI verification is pending.
