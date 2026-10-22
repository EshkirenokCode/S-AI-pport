# S(AI)pport

A support engineer's workspace for investigating SaaS incidents, checking evidence, and approving narrowly scoped repairs.

[![checks](https://github.com/EshkirenokCode/S-AI-pport/actions/workflows/ci.yml/badge.svg)](https://github.com/EshkirenokCode/S-AI-pport/actions/workflows/ci.yml)

![The working support desk](docs/media/workspace.png)

Three workflows share one execution model: a successful payment with missing access, failed integration deliveries, and product configuration questions. Every repair requires a human decision and a fresh state check. The connected business system is a synthetic, stateful HTTP service; it never handles real payments.

## Implementation

Python 3.12, FastAPI, PostgreSQL 17, React, TypeScript, and a real stdio MCP adapter. A durable PostgreSQL worker handles investigations and approved repairs outside HTTP requests. OpenRouter supplies the optional live model; offline runs are explicitly labelled deterministic. Dependency versions are recorded in the Python lock file and npm lockfile.

## Try it

With Docker and Docker Compose installed:

```sh
python3 scripts/configure.py
docker compose up --build --wait
```

Open [the local workspace](http://127.0.0.1:8000). Configuration generates private random secrets in an ignored `.env`. The database and laboratory have no published ports. Starting a demo creates a new isolated workspace with synthetic accounts, 14 tickets, and versioned procedures.

For native development, install Python 3.12+, Node 24+, and PostgreSQL 17:

```sh
make setup
make dev
```

Open [the development workspace](http://127.0.0.1:5173). The script uses its own PostgreSQL cluster on port 55432. Ctrl+C stops the application processes and retains that cluster. See [operations](docs/operations.md) for configuration and recovery.

## Walk through an incident

1. Select **Paid for Pro, still on Free**, then **Start investigation**.
2. Inspect the account/API evidence and the applicable billing procedure. No repair has happened yet.
3. Review the exact event, expected effect, and account version. Choose **Approve & execute**.
4. Watch the operation receipt and fresh verification. The account changes from Free to Pro and the customer reply becomes editable.
5. Try the integration failure and retry-settings question. Permanent credential errors and missing evidence require review.

[Recorded browser walkthrough](docs/media/walkthrough.webm) · [Approval screenshot](docs/media/approval.png) · [Verified repair](docs/media/repair-verified.png) · [Mobile](docs/media/mobile.png)

## Live model

Set `OPENROUTER_API_KEY` in `.env`, restart the API/worker, and choose **Live · OpenRouter free model** in workspace settings. `OPENROUTER_MODEL` defaults to `openrouter/free`. The adapter checks the current zero-price catalog and requires a zero-price provider route. It has no paid fallback.

The live model chooses tools and writes the conclusion. It cannot approve or execute a repair. A run stores each returned model ID, token usage, reported cost, tools, evidence, and outcome. Free-router model selection can change between calls. Availability and rate limits are external dependencies; errors remain visible.

Without a key, the deterministic provider drives the same real APIs, MCP, policy checks, worker, and verification. It is useful for reproducible tests and is visibly labelled **OFFLINE**.

## Verification

```sh
make check
make test
cd frontend && npx playwright install chromium && npm run test:e2e
```

The local development database must be running for integration/browser tests. Tests use separate databases and never call a live model. CI checks the application and a separate Docker Compose workflow.

```sh
make eval                                      # deterministic workflow cases
PYTHONPATH=backend .venv/bin/python scripts/evaluate_retrieval.py
make live                                      # explicit live calls, subject to provider quotas
```

The evaluation harness can reset fixtures only in its newly created local demo workspace. It is not an administrative product endpoint.

Observed development results, 23 October 2026:

| Check | Result | Scope |
| --- | --- | --- |
| Backend | 33 passing tests | Real PostgreSQL, HTTP laboratory and stdio MCP |
| Browser | 6 passing tests | Three families, approval restriction, permanent error, mobile |
| Workflow evaluation | 36/36 expected outcomes; zero duplicate effects | Deterministic driver; 24 development and 12 holdout cases |
| Retrieval | 20/24 expected documents in top three | Four applicable synthetic documents; lexical baseline |
| Live smoke | Billing, delivery and configuration completed | 15 real free-router calls; reported cost $0 |

These are small synthetic checks, not general LLM accuracy or production-impact claims. See [evaluation methodology and raw reports](docs/evaluations.md).

## What the safety boundary does

Every read and mutation is scoped to the authenticated demo workspace. Analysts can investigate; operators can decide on a proposal. An approval binds to an immutable payload and digest. The executor rechecks the approver and account version, uses an external idempotency receipt, and verifies the resulting state. A successful HTTP response without the expected effect is escalated, never shown as a successful repair.

The public repository is runnable; it is not a deployed multi-customer service. The laboratory is synthetic, demo role selection is not production sign-in, retrieval is lexical rather than semantic, and live models can fail. There is no Stripe connector, remote MCP OAuth server, refund capability, or arbitrary URL/SQL/shell execution. See [limitations](docs/limitations.md).

## Design documents

- [Product and delivery plan](docs/plan.md)
- [Architecture and data](docs/architecture.md)
- [API and tool contracts](docs/contracts.md)
- [Permissions and threat model](docs/security.md)
- [Test strategy](docs/testing.md)
- [Architecture decisions](docs/adr/001-execution.md)
- [Retrieval decision](docs/adr/002-retrieval.md)
- [Operations and backup/restore](docs/operations.md)
- [Engineering decisions](docs/engineering.md)

## Author

Ilia Gulevskii · [gulevskii.dev](https://gulevskii.dev/)
