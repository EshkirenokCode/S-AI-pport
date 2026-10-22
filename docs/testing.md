# Test strategy

Business policy is checked with deterministic assertions. Integration tests use real PostgreSQL and a real synthetic SaaS HTTP process. A deterministic model provider drives the same tool contracts and is labelled in the UI; it is not evidence of live-model quality.

Critical checks cover all three families, exact action targets, approval integrity, tenant isolation, role enforcement, receipts/idempotency, competing decisions, stale state, recovery, cancellation, provider errors, unknown tools, and verification failure. Browser tests cover the billing approval path plus integration, documentation, and analyst restrictions.

Evaluation cases are versioned and split into development and holdout sets. Reports separate correct disposition, correct action, final business effect, source grounding, forbidden effects, latency, calls, tokens, and cost. Live results identify the exact returned model and sample count. Offline results must never be presented as measured LLM accuracy.

CI runs backend checks with PostgreSQL, frontend type/build checks, integration tests, and browser end-to-end checks. Live evaluation is explicit and never part of ordinary PR CI.
