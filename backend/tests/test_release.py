import asyncio
from uuid import uuid4

import jwt
import psycopg
from conftest import approve, investigate

from app.db import Database
from app.maintenance import expire_workspaces
from app.services import LabClient


def test_completed_answer_resolves_ticket(client):
    ticket, run = investigate(client, "configuration")
    assert run["status"] == "completed"
    assert client.get("/api/tickets/" + ticket["id"]).json()["ticket"]["status"] == "resolved"


def test_decline_rewrites_pending_conclusion(client):
    ticket, run = investigate(client, "billing_recoverable")
    a = run["actions"][0]
    client.post(
        "/api/actions/" + a["id"] + "/decision", json={"decision": "reject", "digest": a["digest"]}
    ).raise_for_status()
    declined = client.get("/api/runs/" + run["id"]).json()
    assert declined["status"] == "needs_human"
    assert declined["finished_at"]
    assert declined["result"]["disposition"] == "needs_human"
    assert "declined" in declined["result"]["summary"]
    assert "awaiting" not in declined["result"]["reply"]
    detail = client.get("/api/tickets/" + ticket["id"]).json()
    assert detail["ticket"]["status"] == "needs_human"
    assert detail["account"]["plan"] == "Free"


def test_finished_cancel_is_noop(client):
    _, run = investigate(client, "billing_recoverable")
    run = approve(client, run)
    response = client.post("/api/runs/" + run["id"] + "/cancel")
    assert response.json()["status"] == "completed"
    current = client.get("/api/runs/" + run["id"]).json()
    assert current["events"] == run["events"]
    assert current["actions"][0]["status"] == "succeeded"


def test_draft_rejected_before_conclusion(client, stack):
    stack.stop_worker()
    try:
        ticket = client.get("/api/tickets").json()[0]
        rid = client.post("/api/tickets/" + ticket["id"] + "/runs", json={}).json()["id"]
        assert client.patch("/api/runs/" + rid + "/draft", json={"reply": "premature"}).status_code == 409
        client.post("/api/runs/" + rid + "/cancel").raise_for_status()
    finally:
        stack.start_worker()


def test_stale_or_malformed_delegation_is_rejected(client, stack):
    stack.stop_worker()
    try:
        ticket = client.get("/api/tickets").json()[0]
        rid = client.post("/api/tickets/" + ticket["id"] + "/runs", json={}).json()["id"]
        actor = client.get("/api/session").json()
        with psycopg.connect(stack.env["DATABASE_URL"], autocommit=True) as c:
            c.execute(
                "UPDATE runs SET status='running',lease_owner=%s,lease_until=now()+interval '30 seconds' WHERE id=%s",
                (uuid4(), rid),
            )
        claims = {
            "scope": "tools",
            "run": rid,
            "tenant": actor["tenant_id"],
            "actor": actor["id"],
            "lease": str(uuid4()),
            "exp": 4102444800,
        }
        for lease in (str(uuid4()), "malformed"):
            token = jwt.encode({**claims, "lease": lease}, stack.env["APP_SECRET"], algorithm="HS256")
            response = client.post(
                "/api/internal/tools",
                headers={"Authorization": "Bearer " + token},
                json={"name": "get_account_context", "arguments": {}},
            )
            assert response.status_code in (401, 404)
        client.post("/api/runs/" + rid + "/cancel").raise_for_status()
    finally:
        stack.start_worker()


def test_expired_synthetic_workspace_retention(client, stack):
    actor = client.get("/api/session").json()
    tenant = actor["tenant_id"]
    with psycopg.connect(stack.env["DATABASE_URL"], autocommit=True) as c:
        c.execute("UPDATE sessions SET expires_at=now()-interval '1 second' WHERE tenant_id=%s", (tenant,))

    async def clean_expired():
        # Maintenance uses the test services, never the local development tenant.
        db = Database(stack.env["DATABASE_URL"])
        lab = LabClient()
        await lab.close()
        import httpx

        lab.client = httpx.AsyncClient(
            base_url=stack.env["SANDBOX_URL"],
            headers={"Authorization": "Bearer " + stack.env["SANDBOX_TOKEN"]},
        )
        await db.open()
        try:
            await expire_workspaces(db, lab)
        finally:
            await db.close()
            await lab.close()

    asyncio.run(clean_expired())
    assert client.get("/api/session").status_code == 401
    with psycopg.connect(stack.env["DATABASE_URL"]) as c:
        assert not c.execute("SELECT id FROM tenants WHERE id=%s", (tenant,)).fetchone()
    with psycopg.connect(stack.env["SANDBOX_DATABASE_URL"]) as c:
        assert not c.execute("SELECT id FROM accounts WHERE tenant_id=%s", (tenant,)).fetchone()
