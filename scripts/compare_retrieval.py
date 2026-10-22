"""Compare lexical strategies on observed long queries and held-out expansions."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from app.db import Database
from app.fixtures import document_family
from app.retrieval import retrieve
from app.settings import settings
from evaluate_retrieval import CASES as BASELINE_CASES

CASES = [
    (
        "payment succeeded plan upgrade delivery failure",
        "billing",
        "billing-recovery",
        "development",
    ),
    (
        "billing event processing plan upgrade",
        "billing",
        "billing-recovery",
        "development",
    ),
    ("reprocess billing event procedure", "billing", "billing-recovery", "development"),
    (
        "paid invoice entitlement account still free troubleshooting",
        "billing",
        "billing-recovery",
        "holdout",
    ),
    (
        "webhook destination transient unavailable troubleshooting",
        "integration",
        "delivery-recovery",
        "holdout",
    ),
    (
        "where configure endpoint retries policy tutorial",
        "configuration",
        "webhook-settings",
        "holdout",
    ),
]


async def main():
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=20) as c:
        response = c.post("/api/demo/session", json={})
        response.raise_for_status()
        tenant = response.json()["tenant_id"]
    db = Database(settings().database_url)
    await db.open()
    report = {
        "kind": "retrieval_comparison",
        "date": datetime.now(UTC).isoformat(),
        "limitation": "Three observed failure queries plus three authored holdout expansions; small synthetic corpus. Topic metadata is trusted ticket context, not model input.",
        "queries": [],
    }
    try:
        report["original_queries"] = []
        for query, expected in BASELINE_CASES:
            family = document_family(expected)
            family = None if family == "shared" else family
            old = await retrieve(db, tenant, "2.4", query, baseline=True)
            new = await retrieve(db, tenant, "2.4", query, family)
            report["original_queries"].append(
                {
                    "query": query,
                    "expected": expected,
                    "baseline_hit": expected in {d["source_key"] for d in old},
                    "improved_hit": expected in {d["source_key"] for d in new},
                }
            )
        for query, family, expected, split in CASES:
            old = await retrieve(db, tenant, "2.4", query, baseline=True)
            new = await retrieve(db, tenant, "2.4", query, family)
            old_keys, new_keys = (
                [d["source_key"] for d in old],
                [d["source_key"] for d in new],
            )
            report["queries"].append(
                {
                    "query": query,
                    "family": family,
                    "split": split,
                    "expected": expected,
                    "baseline": old_keys,
                    "topic_or_fallback": new_keys,
                    "baseline_hit": expected in old_keys,
                    "improved_hit": expected in new_keys,
                }
            )
    finally:
        await db.close()
    report["summary"] = {
        "queries": len(CASES),
        "baseline_hits_at_3": sum(q["baseline_hit"] for q in report["queries"]),
        "improved_hits_at_3": sum(q["improved_hit"] for q in report["queries"]),
    }
    report["original_summary"] = {
        "queries": len(BASELINE_CASES),
        "baseline_hits_at_3": sum(
            q["baseline_hit"] for q in report["original_queries"]
        ),
        "improved_hits_at_3": sum(
            q["improved_hit"] for q in report["original_queries"]
        ),
    }
    print(report["original_summary"])
    Path("evals/reports/retrieval-comparison.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(report["summary"])


if __name__ == "__main__":
    asyncio.run(main())
