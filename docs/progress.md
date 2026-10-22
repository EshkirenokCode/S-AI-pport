# Delivery progress

## Implemented

- Three ticket families in one React workspace and one persisted execution model.
- FastAPI API, PostgreSQL migrations/leases/checkpoints, a separate stateful HTTP laboratory, and idempotent operation receipts.
- Seven scoped tools through real stdio MCP; immutable proposals, human decisions, fresh authorization/preconditions, and post-action verification.
- Versioned full-text retrieval, exact source dialogs, separate facts/assumptions/missing information, editable replies, audit history, and usage.
- Explicit offline provider and zero-price-only OpenRouter adapter. Prompt revisions are stored under backend/app/prompts and recorded on runs.
- Docker Compose, isolated native startup, CI, operations/recovery/backup documentation, screenshots, and a recorded real browser walkthrough.

## Verified

- 33 backend tests pass with real PostgreSQL, HTTP services, and MCP subprocesses.
- Six browser tests pass, including all three families and mobile.
- 36 deterministic workflow cases: expected outcomes match; no duplicate business effects. This is contract coverage, not LLM accuracy.
- Retrieval baseline: 20/24 expected documents in the top three; the four lexical/paraphrase misses are retained in the report.
- Three canonical live OpenRouter/MCP runs complete; billing and delivery repairs are approved and independently verified. The 15 reported model calls cost $0.
- GitHub Actions application and container jobs pass, including an actual Compose billing repair.
- Tracked files contain no provider credential. Commit author and committer identities are EshkirenokCode.

## Final checks

The additional negative live smoke set and current-prompt smoke report are being finalized. The final delivery commit will be checked in CI.

## Deliberate limits

See limitations.md and evaluations.md. Retrieval is lexical; pgvector/semantic search, Stripe, public hosting, production sign-in, remote MCP OAuth, automatic retention, and scheduled backups are not included. Existing infrastructure and the published portfolio are unchanged.

## Continue

make setup; make dev. Optional live key goes only into the private .env. Public deployment is separate work in an isolated environment.
