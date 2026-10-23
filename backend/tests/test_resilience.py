import time
from uuid import uuid4

import httpx
import jwt
import psycopg
import pytest
from conftest import investigate, wait_run

from app.services import LabClient


def test_missing_sources_escalates(client, stack):
    tenant = client.get("/api/session").json()["tenant_id"]
    with psycopg.connect(stack.env["DATABASE_URL"], autocommit=True) as c:
        c.execute("DELETE FROM documents WHERE tenant_id=%s", (tenant,))
    _, run = investigate(client, "billing_recoverable")
    assert run["status"] == "needs_human"
    assert not run["actions"]


def test_revoked_approver_is_checked_before_execution(client, stack):
    _, run = investigate(client, "billing_recoverable")
    stack.stop_worker()
    try:
        a = run["actions"][0]
        client.post(
            "/api/actions/" + a["id"] + "/decision", json={"decision": "approve", "digest": a["digest"]}
        ).raise_for_status()
        with psycopg.connect(stack.env["DATABASE_URL"], autocommit=True) as c:
            c.execute("UPDATE actors SET role='analyst' WHERE id=%s", (run["actor_id"],))
    finally:
        stack.start_worker()
    result = wait_run(client, run["id"])
    assert result["status"] == "needs_human"
    assert "permission" in result["error"]


def test_operation_receipt_reconciles_worker_crash(client, stack):
    ticket, run = investigate(client, "billing_recoverable")
    a = run["actions"][0]
    stack.stop_worker()
    try:
        client.post(
            "/api/actions/" + a["id"] + "/decision", json={"decision": "approve", "digest": a["digest"]}
        ).raise_for_status()
        body = {k: a["payload"][k] for k in ("account_id", "expected_version")}
        body.update(
            tenant_id=run["tenant_id"], operation_id=a["id"], kind=a["kind"], target_id=a["target_id"]
        )
        headers = {"Authorization": "Bearer " + stack.env["SANDBOX_TOKEN"]}
        # Simulate the HTTP effect occurring before the worker's checkpoint is committed.
        response = httpx.post(stack.env["SANDBOX_URL"] + "/operations", headers=headers, json=body)
        response.raise_for_status()
        assert (
            httpx.post(stack.env["SANDBOX_URL"] + "/operations", headers=headers, json=body).json()
            == response.json()
        )
        with psycopg.connect(stack.env["DATABASE_URL"], autocommit=True) as c:
            c.execute("UPDATE actions SET status='executing' WHERE id=%s", (a["id"],))
            c.execute(
                "UPDATE runs SET status='running',lease_owner=%s,lease_until=now()-interval '1 second',attempts=1 WHERE id=%s",
                (uuid4(), run["id"]),
            )
    finally:
        stack.start_worker()
    recovered = wait_run(client, run["id"])
    assert recovered["status"] == "completed"
    assert recovered["attempts"] == 2
    assert recovered["result"]["verification"]["verified"]
    with psycopg.connect(stack.env["SANDBOX_DATABASE_URL"]) as c:
        assert (
            c.execute("SELECT version FROM accounts WHERE id=%s", (ticket["account_id"],)).fetchone()[0] == 2
        )


def test_deadline_and_acquisition_budget(client, stack):
    stack.stop_worker()
    ids = []
    try:
        for ticket in client.get("/api/tickets").json()[:2]:
            rid = client.post("/api/tickets/" + ticket["id"] + "/runs", json={}).json()["id"]
            ids.append(rid)
        with psycopg.connect(stack.env["DATABASE_URL"], autocommit=True) as c:
            c.execute("UPDATE runs SET deadline=now()-interval '1 second' WHERE id=%s", (ids[0],))
            c.execute("UPDATE runs SET attempts=3 WHERE id=%s", (ids[1],))
    finally:
        stack.start_worker()
    assert "time budget" in wait_run(client, ids[0])["error"]
    assert "Recovery attempt budget" in wait_run(client, ids[1])["error"]


def test_unknown_evidence_and_wrong_source_version(client, stack):
    stack.stop_worker()
    try:
        ticket = client.get("/api/tickets").json()[2]
        rid = client.post("/api/tickets/" + ticket["id"] + "/runs", json={}).json()["id"]
        with psycopg.connect(stack.env["DATABASE_URL"], autocommit=True) as c:
            tenant, actor = c.execute("SELECT tenant_id,actor_id FROM runs WHERE id=%s", (rid,)).fetchone()
            lease = uuid4()
            c.execute(
                "UPDATE runs SET status='running',lease_owner=%s,lease_until=now()+interval '20 seconds' WHERE id=%s",
                (lease, rid),
            )
            old = str(
                c.execute(
                    "SELECT id FROM documents WHERE tenant_id=%s AND product_version='1.8'", (tenant,)
                ).fetchone()[0]
            )
        token = jwt.encode(
            {
                "scope": "tools",
                "lease": str(lease),
                "tenant": str(tenant),
                "actor": str(actor),
                "run": rid,
                "exp": time.time() + 30,
            },
            stack.env["APP_SECRET"],
            algorithm="HS256",
        )
        headers = {"Authorization": "Bearer " + token}
        r = client.post(
            "/api/internal/tools",
            headers=headers,
            json={"name": "read_document", "arguments": {"document_id": old}},
        )
        assert "does not apply" in r.json()["error"]
        r = client.post(
            "/api/internal/tools",
            headers=headers,
            json={
                "name": "finish_investigation",
                "arguments": {
                    "disposition": "resolved",
                    "summary": "An invented conclusion.",
                    "facts": [],
                    "missing_information": [],
                    "source_ids": ["fabricated"],
                    "reply": "Invented answer.",
                },
            },
        )
        assert "Unknown evidence" in r.json()["error"]
        client.post("/api/runs/" + rid + "/cancel")
    finally:
        stack.start_worker()


@pytest.mark.asyncio
async def test_http_read_retry_classification():
    lab = LabClient()
    await lab.close()
    calls = []

    async def transient(request):
        calls.append(1)
        return httpx.Response(503 if len(calls) < 3 else 200, json={"ok": True})

    lab.client = httpx.AsyncClient(transport=httpx.MockTransport(transient), base_url="http://laboratory")
    try:
        assert await lab.get("/state") == {"ok": True}
        assert len(calls) == 3
    finally:
        await lab.close()
    calls.clear()

    async def permanent(request):
        calls.append(1)
        return httpx.Response(401)

    lab.client = httpx.AsyncClient(transport=httpx.MockTransport(permanent), base_url="http://laboratory")
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await lab.get("/state")
        assert len(calls) == 1
    finally:
        await lab.close()


def test_long_query_fallback_uses_trusted_ticket_topic(client, stack):
    import asyncio

    from app.db import Database
    from app.retrieval import retrieve

    tenant = client.get("/api/session").json()["tenant_id"]

    async def check():
        db = Database(stack.env["DATABASE_URL"])
        await db.open()
        try:
            query = "payment succeeded plan upgrade delivery failure"
            assert not await retrieve(db, tenant, "2.4", query, baseline=True)
            rows = await retrieve(db, tenant, "2.4", query, "billing")
            assert "billing-recovery" in {r["source_key"] for r in rows}
            assert not {"delivery-recovery", "webhook-settings"} & {r["source_key"] for r in rows}
        finally:
            await db.close()

    asyncio.run(check())
