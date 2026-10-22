# Known limitations

- The business system is a synthetic HTTP laboratory, including its payment records. There is no Stripe connector and no real financial operation.
- Demo workspace creation and role selection are intentional fixtures. They are not a production login or customer onboarding system.
- Retrieval is PostgreSQL full-text search with product-version filtering. Semantic embeddings, pgvector, a reranker, and hybrid search are not implemented. Four paraphrase queries miss in the recorded baseline.
- Live-model smoke tests cover three canonical workflows and a small separate negative set. They cannot establish general accuracy or prompt-injection robustness. Source-ID validation establishes reference integrity, not formal textual entailment.
- OpenRouter free-router aliases, latency, rate limits, and availability can change. Live errors are visible. There is no paid fallback or automatic paid upgrade.
- The cumulative model-token limit uses observed usage and may be crossed by the final bounded response. No cost estimate is invented when the provider omits cost.
- Waiting for approval is durable, but an approval is only a demo operator decision. An actual customer support deployment would need an external identity provider, stronger account provisioning, and organizational policies.
- Receipt reconciliation supports the included laboratory API. A third-party connector must implement comparable idempotency and reconciliation contracts before mutation is enabled.
- Cancellation cannot undo an already-applied external effect. An in-flight approved operation is reconciled and verified before its outcome is reported.
- Readiness checks cover PostgreSQL and the laboratory, not worker liveness. Run history and lease recovery expose stalled work; no external paging system is configured.
- Expired sessions are rejected, but automatic retention/purging and scheduled backups are not implemented. The standalone demo needs operational retention limits before large-scale public use.
- The recorded walkthrough uses the clearly labelled deterministic driver. Separate raw reports prove the real-model/MCP smoke runs.
- Docker Compose is verified in GitHub Actions. This workstation does not have Docker installed; native integration and browser tests run locally.
- Public hosting and changes to the existing portfolio are separate work.
