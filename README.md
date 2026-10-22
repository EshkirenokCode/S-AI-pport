# S(AI)pport

A support engineer's workspace for investigating SaaS incidents, checking evidence, and approving narrowly scoped repairs.

Three workflows share one execution model: a successful payment with missing access, failed integration deliveries, and product configuration questions. Every repair requires a human decision and a fresh state check. The connected business system is a synthetic, stateful HTTP service; it never handles real payments.

## Implementation

Python 3.12, FastAPI, PostgreSQL, React, TypeScript, and an MCP tool adapter. OpenRouter supplies the optional live model; offline runs are explicitly labelled deterministic. The project is under active development. See [progress](docs/progress.md) for completed and verified capabilities.

## Design documents

- [Product and delivery plan](docs/plan.md)
- [Architecture and data](docs/architecture.md)
- [API and tool contracts](docs/contracts.md)
- [Permissions and threat model](docs/security.md)
- [Test strategy](docs/testing.md)
- [Architecture decisions](docs/adr/001-execution.md)

## Author

Ilia Gulevskii · [gulevskii.dev](https://gulevskii.dev/)
