# ADR 005: retain the measured lexical baseline

Status: accepted for version one.

The initial proposal included pgvector. The implemented corpus has four applicable, concise documents and one legacy version. PostgreSQL full-text search gives 20/24 expected sources in the top three on the recorded query set and excludes the legacy version. The four misses are vocabulary/paraphrase challenges, recorded in the raw report.

Live testing then exposed a concrete failure: long conjunctive queries returned no document, and a changing free-router model switched from billing to delivery. Backend policy rejected those proposals, but the run exhausted its budget.

Add a trusted ticket-topic filter and use an OR fallback only when the original full-text query has no matches. The topic is backend context, never a model argument. The same original query set improves from 20/24 to 21/24 expected documents at three. Three observed long queries plus three authored holdout expansions improve from 0/6 to 6/6. A regression test checks that a mixed billing/delivery query cannot retrieve the unrelated delivery procedure for a billing ticket.

Retain this improved lexical retriever for version one. It requires no embedding model download, paid embedding endpoint, vector migration, or reranker. This is retrieval-augmented generation with versioned sources, not semantic search. Three original vocabulary gaps remain. Lack of a matching source leads to clarification/review; the agent can reformulate a query within its call budget.

pgvector and locally generated semantic embeddings remain a possible measured improvement if corpus size or paraphrase coverage warrants them. They are not implemented or advertised as completed features. A larger independently authored holdout set should precede that decision.
