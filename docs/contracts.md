# API and tool contracts

All workspace routes derive tenant and actor from the session. UUIDs alone never authorize access. Unknown request fields are rejected. All timestamps use UTC.

| Route | Contract |
| --- | --- |
| POST /api/demo/session | Create an isolated synthetic workspace and operator or analyst session |
| GET /api/session | Session, role, tenant, configured provider |
| GET /api/tickets | Tenant-scoped queue |
| GET /api/tickets/{id} | Ticket, account context, latest run |
| POST /api/tickets/{id}/runs | Queue a bounded investigation; reuse an active run |
| GET /api/runs/{id} | Durable state, observable events, proposals, result |
| GET /api/runs/{id}/events | SSE with Last-Event-ID replay and heartbeat |
| POST /api/runs/{id}/cancel | Request cancellation, invalidate pending proposals |
| POST /api/actions/{id}/decision | Approve/reject exact proposal digest; operator required |
| PATCH /api/runs/{id}/draft | Save an edited customer reply |
| GET /api/documents/{id} | Authorized versioned document source |
| GET /api/metrics | Tenant run and usage summary |
| GET /health, /ready | Liveness and dependency readiness |

## Run state

queued → running → waiting_for_approval → queued (execution) → running → completed / needs_human / failed / cancelled. An investigation can also finish without an action. Terminal states are immutable except for editing a reply. Events expose checks, API facts, source excerpts, decisions, and verification; hidden model reasoning is not returned.

## Model tools

| Name | Inputs | Policy |
| --- | --- | --- |
| get_account_context | none | Read current ticket account |
| get_billing_state | none | Read current account billing |
| get_delivery_state | none | Read current account integration |
| search_documentation | query | Tenant/version-filtered bounded retrieval |
| read_document | document_id | Exact authorized source |
| propose_action | kind, target_id | Backend derives immutable parameters/preconditions |
| finish_investigation | disposition, summary, facts, missing_information, source_ids, reply | Validate references and proposal consistency |

Tool arguments cannot select tenant, actor, a URL, file, SQL, or shell command. Calls and outcomes are stored as evidence. Model-supplied action parameters never replace trusted preconditions.
