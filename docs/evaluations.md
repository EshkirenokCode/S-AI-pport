# Evaluation methodology

The reports under `evals/reports/` are machine-readable records from the running system. Dates in JSON use UTC. The development session was 23 October 2026 in Asia/Bangkok.

## Workflow contracts

`workflows-v1.json` contains 36 synthetic cases: 24 development and 12 holdout cases. The deterministic driver selects tools from their actual observations. The API, PostgreSQL queue, MCP subprocess, laboratory HTTP operations, approval policy, and verification all run normally.

The harness resets only its own fixtures. It checks terminal disposition, absence of repeated effects, successful post-action verification where appropriate, analyst approval denial, and evidence presence. The recorded result is 36 expected outcomes, zero duplicate effects, and five verified repairs. Failure to restore an entitlement is correctly escalated.

This report measures the backend/workflow contract. Because the provider is deterministic, injection cases here do not prove a language model resists adversarial instructions. The holdout set is checked separately in the report but remains a small authored test set rather than an independent benchmark.

## Live model smoke tests

`live-billing.json` and `live-smoke.json` record one real run for each family using OpenRouter's free router, with stdio MCP. Billing used six calls, delivery five, configuration four. Both business operations were approved and verified with fresh reads. All 15 calls reported zero cost.

The router can choose different models between calls. Each actual returned model, input/output token count, latency, and reported cost appears in the report. These IDs are provider aliases, not immutable weight snapshots. No hidden model reasoning or credential is published.

`live-safety.json` records three additional negative cases. The analyst/injection case stopped at the model-call limit; the credential-error case requested human review; the unconfirmed-payment case stopped on an upstream timeout. All three left the account at version one with no business effect. The two interrupted investigations are not counted as successful semantic conclusions. Live failures remain in the report; infrastructure failure is not silently converted into success.

`live-current-prompt.json` separately records the check against the current prompt revision. The original three canonical reports use support-v1; later revisions are stored alongside that prompt for comparison.

The sample is too small to estimate broad accuracy, reliability, or prompt-injection resistance. Live evaluation is explicit and not run in ordinary CI. Free-model quotas and availability can change.

## Retrieval

`retrieval-baseline.json` calls the same production `retrieve` function with 24 fixed queries, split into development and holdout queries. Expected-document recall at three is 20/24. Four literal vocabulary/paraphrase challenges miss. Version filtering excludes the product 1.8 instructions from 2.4 results.

The corpus is four applicable synthetic documents. This result is not a comparison against embedding retrieval or a claim of production search quality. See the [retrieval ADR](adr/002-retrieval.md).

## Reproduction

Start the local stack, then run `make eval`, `scripts/evaluate_retrieval.py` with `PYTHONPATH=backend`, or `make live`. Raw evaluation files are overwritten by these explicit commands. Tests use separate databases. Keep live API credentials private in `.env`.
