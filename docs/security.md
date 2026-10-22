# Permissions and threat model

| Operation | Analyst | Operator | Model |
| --- | --- | --- | --- |
| Read own tickets, sources, runs | Yes | Yes | Through scoped tools |
| Start/cancel investigation | Yes | Yes | No |
| Propose eligible repair | Yes | Yes | Through policy |
| Approve/reject repair | No | Yes | No |
| Execute approved repair | Worker only | Worker only | No |
| Read another workspace | No | No | No |
| Change credentials, charges, refunds, roles | No | No | No |

Anonymous demo visitors receive an isolated synthetic tenant and an expiring session. Role selection is a demo fixture, not production authentication. Public exposure requires quotas, secure cookies, explicit trusted-proxy configuration, and a separate environment. Administrative database access is never a tool.

## Trust boundaries

- Tickets, documents, external API fields, and tool text are untrusted evidence. They cannot confer permissions or approve actions.
- Every object query includes tenant scope, including source retrieval and SSE replay.
- Proposals bind kind, target, parameters, expected state version, and a digest. Decisions require the displayed digest and backend role checks.
- The worker rechecks the approving actor's membership and the operation's preconditions immediately before execution.
- Unknown external results are reconciled by operation receipt and fresh state reads. No blind repeat of a mutation.
- No arbitrary endpoints, commands, database queries, or model-selected identity.
- Logs omit credentials and raw authorization headers. Browser data excludes provider secrets and model reasoning.
- Session creation, queued runs, live model calls, concurrent investigations, elapsed time, and tool counts have limits.

## Negative verification

Cross-tenant IDs, insufficient role, forged confirmation in a ticket, changed proposal digest, stale source/state, simultaneous approval, duplicate jobs, transient/permanent HTTP failures, injected instructions, missing evidence, cancellation, lease recovery, exhausted budgets, malformed tool calls, and failed post-action verification.
