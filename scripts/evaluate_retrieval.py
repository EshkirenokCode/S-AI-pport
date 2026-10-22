"""Measure the production retrieval function with literal, versioned queries."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from app.db import Database
from app.retrieval import retrieve
from app.settings import settings

CASES = [
    ("paid subscription", "billing-recovery"),
    ("billing event failed", "billing-recovery"),
    ("payment succeeded Free", "billing-recovery"),
    ("reprocess billing event", "billing-recovery"),
    ("missing invoice event", "billing-recovery"),
    ("entitlements Pro", "billing-recovery"),
    ("payment pending", "billing-recovery"),
    ("verify entitlement", "billing-recovery"),
    ("webhook deliveries", "delivery-recovery"),
    ("integration unauthorized", "delivery-recovery"),
    ("destination acknowledgement", "delivery-recovery"),
    ("retry delivery cooldown", "delivery-recovery"),
    ("429 retry_after", "delivery-recovery"),
    ("credentials configuration", "delivery-recovery"),
    ("configure webhook retries", "webhook-settings"),
    ("Retry attempts", "webhook-settings"),
    ("Delivery policy", "webhook-settings"),
    ("exponential backoff", "webhook-settings"),
    ("support roles approvals", "permissions"),
    ("immutable repair proposal", "permissions"),
    ("my upgrade vanished", "billing-recovery"),
    ("events are stuck in transit", "delivery-recovery"),
    ("where are the resend options", "webhook-settings"),
    ("who can authorize remediation", "permissions"),
]


async def main():
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=20) as client:
        tenant = client.post("/api/demo/session", json={}).json()["tenant_id"]
    db = Database(settings().database_url)
    await db.open()
    report = {
        "kind": "retrieval_baseline",
        "date": datetime.now(UTC).isoformat(),
        "retriever": "postgresql_fts_v1",
        "corpus": "4 applicable synthetic documents; one legacy version excluded",
        "limitations": "Small hand-written query set; final four queries are vocabulary/paraphrase challenges. No semantic retrieval claim.",
        "queries": [],
    }
    try:
        for i, (query, expected) in enumerate(CASES):
            rows = await retrieve(db, tenant, "2.4", query, baseline=True)
            keys = [r["source_key"] for r in rows]
            report["queries"].append(
                {
                    "query": query,
                    "split": "development" if i < 16 else "holdout",
                    "expected": expected,
                    "results": keys,
                    "hit_at_3": expected in keys,
                }
            )
        old = await retrieve(db, tenant, "2.4", "five retries")
        report["legacy_source_excluded"] = not any(r["version"] == "1.8" for r in old)
    finally:
        await db.close()
    report["summary"] = {
        "queries": len(CASES),
        "hits_at_3": sum(q["hit_at_3"] for q in report["queries"]),
    }
    Path("evals/reports/retrieval-baseline.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )
    print(report["summary"])


if __name__ == "__main__":
    asyncio.run(main())
