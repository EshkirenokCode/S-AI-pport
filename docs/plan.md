# Product and delivery plan

## Outcome

Help a support operator establish what happened, find an applicable procedure, approve one exact repair, and verify its effect. A run may also ask for clarification, escalate, fail, or be cancelled. Evidence and execution history remain inspectable.

The workspace is the product. A ticket queue, account context, investigation timeline, evidence, approval panel, and editable customer reply are the primary interface. UI and public documentation are in English.

## Version one

1. **Foundation.** Record architecture, contracts, permissions, testing, and implementation milestones.
2. **Billing vertical.** Stateful test SaaS, migrations, API, durable worker, offline tool provider, and a working approval/repair/verification flow.
3. **Live investigation.** OpenRouter free-model integration, bounded tool use, versioned retrieval, and real stdio MCP calls.
4. **Coverage and reliability.** Integration and configuration workflows, two-tenant tests, roles, immutable proposals, retry/recovery/cancellation, and negative cases.
5. **Product and measurement.** Complete responsive interface, meaningful browser tests, development and holdout evaluation cases, observability, CI, and reproducible startup.
6. **Delivery.** Screenshots and a walkthrough from the running product; deployment, backup/restore, limitations, and results documentation.

Each milestone is committed and pushed separately. Keep the repository runnable and record verification in progress.md.

## Acceptance

- A clean checkout starts using documented commands and synthetic data.
- All three workflows are exercised through the browser.
- Billing really reads HTTP state, proposes a specific operation, waits for approval, executes idempotently, and re-reads the result.
- Waiting and active jobs survive worker restarts with bounded recovery.
- A live model and a real MCP exchange are verified separately from offline tests.
- Prepared isolation, permissions, injection, duplicate-click, concurrency, stale-state, and failed-verification cases pass.
- Evaluation reports identify provider, model, prompt version, dataset, date, sample size, and limitations.
- No secrets are committed or included in browser assets or logs.

## Boundaries

No real financial operations, arbitrary code/SQL/URL execution, production customer data, or modifications to existing services. Public hosting and the existing portfolio are separate deployment work. A missing live credential does not block implementation but does block claiming live verification.
