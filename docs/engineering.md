# Engineering decisions and contribution

This repository implements the product model, Python HTTP services, PostgreSQL migrations and workflow, scoped tools and MCP transport, OpenRouter integration, retrieval, React workspace, test fixtures, evaluation harnesses, and deployment configuration.

The main design choices are observable in the code and tests:

1. **One approval binds one operation.** Immutable proposals, digests, fresh authorization and version checks prevent a model suggestion or repeated click from broadening the approved effect.
2. **HTTP success is not the result.** The laboratory stores independent operation receipts. The worker reconciles uncertain responses and reads account/delivery state again. The failed-verification fixture demonstrates why a receipt alone is insufficient.
3. **Persistence owns the workflow.** Queue leases, checkpoints and approval transitions live in PostgreSQL. A restart is an expected transition rather than a lost in-memory conversation.
4. **MCP adapts an existing boundary.** The stdio server forwards a signed run context to the same registry. It does not duplicate policy or give the model tenant/actor selection.
5. **Tests and model evidence are distinct.** Deterministic tests verify contracts and business effects. Live reports identify the actual free-router models and their observed behavior. Neither is described as production experience or broad accuracy.
6. **The work surface is the interface.** The ticket queue, evidence timeline, exact approval and checked outcome take priority over a free-form chatbot or marketing page. The SPA is served by the existing API in production.

Tradeoffs include an explicit workflow implementation instead of a workflow platform, lexical retrieval for a small versioned corpus, a private stdio adapter instead of remote MCP/OAuth, and a synthetic payment source instead of an external paid integration. Known limits and measured misses are recorded rather than hidden behind success counters.
