# Public demo audit — 0.2.0

Reviewed on 23 October 2026: application/API routes, schemas, permissions, worker execution and recovery, MCP delegation, retrieval/provider adapters, migrations, stateful laboratory, React state, responsive UI, browser behavior, dependency declarations, container configuration, and deployment boundaries.

## Corrected behavior

| Finding | Resolution | Regression evidence |
| --- | --- | --- |
| Completed answers left tickets open | The owning worker commits run and ticket status together | `test_completed_answer_resolves_ticket` |
| Decline retained an awaiting-approval conclusion | Store a final review disposition, revised draft, and completion time | Backend and browser decline checks |
| Cancellation wrote false records or retained an approval draft | Terminal/repeated cancellation returns the existing state; cancelled proposals get a final conclusion | `test_finished_cancel_is_noop` |
| In-progress draft writes could be overwritten | Reject writes before findings; audit accepted saves | `test_draft_rejected_before_conclusion` |
| Browser responses could target the newly selected ticket | Bind mutation responses to their original ticket/run | Browser switching/draft regression |
| Unsaved edits vanished on navigation/reload | Keep per-run edits in tab-scoped session storage until explicitly saved | Browser draft recovery check |
| Old MCP delegation survived a change of worker ownership | Require and validate the current lease owner | Stale/malformed delegation test |
| A worker losing its lease could still finalize related state | Lock and validate ownership before finalization; guard tool result/proposal writes | Existing recovery checks plus delegation regression |
| Assumptions appeared current after a repair | Label pre-repair assumptions historically; separate post-action verification | Verified-result view |
| Network errors provisioned redundant demo tenants | Provision only after an authenticated 401, and expose boot retry | Browser outage recovery check |
| Dialog keyboard navigation could leave the modal | Native dialog, explicit Tab boundary handling, Escape and focus restoration | Keyboard regression test |
| Account context disappeared on narrow screens | Add an explicit account-details panel and close control | 320, 390, 768, and 1024px browser checks |
| Critical action followed the full technical event log | Put findings and proposal first; make activity inspectable below | Updated approval screenshots |
| The public demo had no global provisioning/queue cap or retention | Add database-enforced global caps and bounded cleanup of expired synthetic workspaces | Retention regression; deployment configuration |
| Small, low-contrast text and a decorative shell competed with the work | New composition, local IBM Plex typography, contrast corrections, coherent responsive states | Automated WCAG A/AA checks on workspace, approval and settings |
| MCP task groups hid upstream access errors | Unwrap nested exceptions and return an actionable, sanitized provider outcome | Wrapped HTTP 401/403/429 and policy regression |
| Hosted Live could be selected despite a provider network restriction | Disable Live per deployment, enforce it in the API, explain the reason, and default to Offline | Browser restriction check and public session API |
| Runtime imported JWT through a transitive dependency | Declare PyJWT directly | Dependency check and installation lock |

## Validation

- 41 backend tests pass with PostgreSQL, the separate HTTP laboratory, and real stdio MCP.
- 13 browser scenarios pass, including automated accessibility checks. This does not replace manual assistive-technology testing.
- 36 deterministic evaluation cases produce the expected disposition with no duplicate effects.
- TypeScript/Vite production build and Python lint pass.
- npm reports no known vulnerabilities in the installed dependency set at the time of checking.
- Public deployment validation is recorded in `deploy/README.md` after rollout.

## Remaining product boundaries

Accounts and payments are synthetic. Role selection is a demo fixture. Documentation retrieval is lexical. The integration acknowledgement is simulated by the laboratory. The hosted demo is explicitly Offline because OpenRouter returns HTTP 403 from that server network. Local Live remains supported. Free model availability is external, and a model can still exhaust its budget or reach an incorrect conclusion. Backend action eligibility and verification remain deterministic boundaries. Customer replies are drafts, and no external messaging connector is implemented.

The audit fixes identified defects within this release's scope; it is not a claim that the application has no remaining defects or is ready for arbitrary production integrations.
