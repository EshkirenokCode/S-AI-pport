import asyncio
import hashlib
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from psycopg.errors import UniqueViolation

from app.db import Database, clean, js
from app.providers import PROMPT_VERSION
from app.schemas import Decision, DemoSession, Draft, StartRun, Strict
from app.services import LabClient, create_workspace, identity, rate_limit, read_delegation
from app.settings import ROOT, settings
from app.tools import ToolRegistry

cfg = settings()


@asynccontextmanager
async def lifespan(app):
    app.state.db = Database(cfg.database_url)
    await app.state.db.open()
    app.state.lab = LabClient()
    app.state.tools = ToolRegistry(app.state.db, app.state.lab)
    yield
    await app.state.lab.close()
    await app.state.db.close()


app = FastAPI(title="S(AI)pport", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def security(request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin not in cfg.allowed_origins.split(","):
            return Response("Untrusted origin", status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
async def ready(request: Request):
    await request.app.state.db.one("SELECT 1")
    r = await request.app.state.lab.client.get("/health")
    r.raise_for_status()
    return {"status": "ready"}


@app.post("/api/demo/session")
async def demo(body: DemoSession, request: Request, response: Response):
    ip = hashlib.sha256((request.client.host if request.client else "unknown").encode()).hexdigest()
    await rate_limit(request.app.state.db, "session:" + ip, cfg.session_limit_per_hour)
    await rate_limit(request.app.state.db, "session:global", cfg.global_sessions_per_hour)
    token, tenant = await create_workspace(request.app.state.db, request.app.state.lab, body.role)
    response.set_cookie(
        "saipport_session",
        token,
        httponly=True,
        secure=cfg.secure_cookies,
        samesite="strict",
        max_age=cfg.session_hours * 3600,
        path="/",
    )
    return {"tenant_id": tenant, "role": body.role}


@app.get("/api/session")
async def session(actor=Depends(identity)):
    return {
        **actor,
        "provider": cfg.model_provider,
        "transport": cfg.tool_transport,
        "live_available": bool(cfg.openrouter_api_key.get_secret_value()),
        "synthetic": True,
    }


@app.get("/api/tickets")
async def tickets(request: Request, actor=Depends(identity)):
    return await request.app.state.db.all(
        """SELECT t.*,r.id AS run_id,r.status AS run_status FROM tickets t
        LEFT JOIN LATERAL(SELECT id,status FROM runs WHERE ticket_id=t.id AND tenant_id=t.tenant_id
        ORDER BY created_at DESC LIMIT 1) r ON true WHERE t.tenant_id=%s ORDER BY t.number""",
        (actor["tenant_id"],),
    )


@app.get("/api/tickets/{ticket_id}")
async def ticket(ticket_id: UUID, request: Request, actor=Depends(identity)):
    db = request.app.state.db
    row = await db.one("SELECT * FROM tickets WHERE id=%s AND tenant_id=%s", (ticket_id, actor["tenant_id"]))
    if not row:
        raise HTTPException(404, "Ticket not found")
    state = await request.app.state.lab.state(actor["tenant_id"], row["account_id"])
    run = await db.one(
        "SELECT id FROM runs WHERE ticket_id=%s AND tenant_id=%s ORDER BY created_at DESC LIMIT 1",
        (ticket_id, actor["tenant_id"]),
    )
    return {"ticket": row, "account": state, "run_id": run["id"] if run else None}


@app.post("/api/tickets/{ticket_id}/runs", status_code=202)
async def start(ticket_id: UUID, body: StartRun, request: Request, actor=Depends(identity)):
    db = request.app.state.db
    ticket = await db.one(
        "SELECT id FROM tickets WHERE id=%s AND tenant_id=%s", (ticket_id, actor["tenant_id"])
    )
    if not ticket:
        raise HTTPException(404, "Ticket not found")
    active = await db.one(
        "SELECT id FROM runs WHERE ticket_id=%s AND tenant_id=%s AND status IN ('queued','running','waiting_for_approval')",
        (ticket_id, actor["tenant_id"]),
    )
    if active:
        return active
    provider = body.provider or cfg.model_provider
    if provider == "openrouter" and not cfg.openrouter_api_key.get_secret_value():
        raise HTTPException(503, "OpenRouter key is not configured. Offline mode remains available.")
    async with db.pool.connection() as c, c.transaction():
        await c.execute("SELECT pg_advisory_xact_lock(928104)")
        global_count = await (
            await c.execute("SELECT count(*) AS n FROM runs WHERE status IN ('queued','running')")
        ).fetchone()
        if global_count["n"] >= cfg.global_active_runs:
            raise HTTPException(429, "The demo is busy. Try again in a moment.")
        await c.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(actor["tenant_id"]),))
        counts = await (
            await c.execute(
                """SELECT count(*) AS total,count(*) FILTER(WHERE status IN ('queued','running')) AS active
            FROM runs WHERE tenant_id=%s""",
                (actor["tenant_id"],),
            )
        ).fetchone()
        if counts["total"] >= cfg.runs_per_tenant or counts["active"] >= 3:
            raise HTTPException(429, "Workspace run quota reached")
        await c.execute(
            "UPDATE tickets SET status='open' WHERE id=%s AND tenant_id=%s", (ticket_id, actor["tenant_id"])
        )
        run_id = uuid4()
        try:
            await c.execute(
                """INSERT INTO runs(id,tenant_id,ticket_id,actor_id,provider,deadline,prompt_version)
                VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (
                    run_id,
                    actor["tenant_id"],
                    ticket_id,
                    actor["id"],
                    provider,
                    datetime.now(UTC) + timedelta(seconds=cfg.run_timeout_seconds),
                    PROMPT_VERSION,
                ),
            )
        except UniqueViolation:
            raise HTTPException(409, "An investigation is already active") from None
    await db.audit(actor["tenant_id"], actor["id"], "investigation.queued", run_id, run_id)
    return {"id": run_id}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: UUID, request: Request, actor=Depends(identity)):
    db = request.app.state.db
    run = await db.one(
        """SELECT id,tenant_id,ticket_id,actor_id,provider,model,prompt_version,status,phase,
        attempts,result,error,cancel_requested,created_at,started_at,finished_at FROM runs WHERE id=%s AND tenant_id=%s""",
        (run_id, actor["tenant_id"]),
    )
    if not run:
        raise HTTPException(404, "Run not found")
    events = await db.all(
        "SELECT * FROM events WHERE run_id=%s AND tenant_id=%s ORDER BY id", (run_id, actor["tenant_id"])
    )
    actions = await db.all(
        "SELECT * FROM actions WHERE run_id=%s AND tenant_id=%s", (run_id, actor["tenant_id"])
    )
    usage = await db.all(
        "SELECT model,input_tokens,output_tokens,cost,duration_ms FROM model_calls WHERE run_id=%s", (run_id,)
    )
    return {**run, "events": events, "actions": actions, "usage": usage}


@app.get("/api/runs/{run_id}/events")
async def stream(
    run_id: UUID, request: Request, last_event_id: str = Header(default="0"), actor=Depends(identity)
):
    db = request.app.state.db
    exists = await db.one("SELECT id FROM runs WHERE id=%s AND tenant_id=%s", (run_id, actor["tenant_id"]))
    if not exists:
        raise HTTPException(404, "Run not found")
    try:
        cursor = max(0, int(last_event_id))
    except ValueError:
        raise HTTPException(400, "Invalid Last-Event-ID") from None

    async def events():
        nonlocal cursor
        for _ in range(600):
            if await request.is_disconnected():
                return
            rows = await db.all(
                "SELECT * FROM events WHERE run_id=%s AND tenant_id=%s AND id>%s ORDER BY id LIMIT 100",
                (run_id, actor["tenant_id"], cursor),
            )
            for row in rows:
                cursor = row["id"]
                yield f"id: {cursor}\ndata: {json.dumps(clean(row))}\n\n"
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(events(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


@app.post("/api/runs/{run_id}/cancel")
async def cancel(run_id: UUID, request: Request, actor=Depends(identity)):
    db = request.app.state.db
    async with db.pool.connection() as c, c.transaction():
        run = await (
            await c.execute(
                "SELECT * FROM runs WHERE id=%s AND tenant_id=%s FOR UPDATE", (run_id, actor["tenant_id"])
            )
        ).fetchone()
        if not run:
            raise HTTPException(404, "Run not found")
        if run["cancel_requested"] or run["status"] not in ("queued", "running", "waiting_for_approval"):
            return {"cancel_requested": run["cancel_requested"], "status": run["status"]}
        if run["status"] in ("queued", "running", "waiting_for_approval"):
            # An in-flight external effect must still be reconciled by the executor.
            executing = run["status"] == "running" and run["phase"] == "execute"
            await c.execute(
                "UPDATE runs SET cancel_requested=true,status=CASE WHEN %s THEN status ELSE 'cancelled' END,finished_at=CASE WHEN %s THEN finished_at ELSE now() END WHERE id=%s",
                (executing, executing, run_id),
            )
            await c.execute(
                "UPDATE actions SET status='cancelled' WHERE run_id=%s AND status IN ('pending','approved')",
                (run_id,),
            )
            if not executing:
                await c.execute(
                    "UPDATE tickets SET status='open' WHERE id=%s AND tenant_id=%s",
                    (run["ticket_id"], actor["tenant_id"]),
                )
    await db.event(run, "cancelled", "Cancellation requested")
    await db.audit(actor["tenant_id"], actor["id"], "investigation.cancelled", run_id, run_id)
    return {"cancel_requested": True}


@app.post("/api/actions/{action_id}/decision")
async def decide(action_id: UUID, body: Decision, request: Request, actor=Depends(identity)):
    if actor["role"] != "operator":
        raise HTTPException(403, "An operator must approve or reject repairs")
    db = request.app.state.db
    async with db.pool.connection() as c, c.transaction():
        reference = await (
            await c.execute(
                "SELECT run_id FROM actions WHERE id=%s AND tenant_id=%s", (action_id, actor["tenant_id"])
            )
        ).fetchone()
        if not reference:
            raise HTTPException(404, "Proposal not found")
        run = await (
            await c.execute(
                "SELECT * FROM runs WHERE id=%s AND tenant_id=%s FOR UPDATE",
                (reference["run_id"], actor["tenant_id"]),
            )
        ).fetchone()
        action = await (
            await c.execute(
                "SELECT * FROM actions WHERE id=%s AND tenant_id=%s FOR UPDATE",
                (action_id, actor["tenant_id"]),
            )
        ).fetchone()
        if body.digest != action["digest"]:
            raise HTTPException(409, "Proposal digest does not match the displayed action")
        wanted = "approved" if body.decision == "approve" else "rejected"
        if action["status"] != "pending":
            if action["status"] in (wanted, "executing", "succeeded") and body.decision == "approve":
                return {"status": action["status"], "run_id": action["run_id"]}
            raise HTTPException(409, "This proposal already has a decision")
        if run["status"] != "waiting_for_approval" or run["cancel_requested"]:
            raise HTTPException(409, "Run is not waiting for approval")
        await c.execute(
            "UPDATE actions SET status=%s,approved_by=%s,approved_at=now() WHERE id=%s",
            (wanted, actor["id"], action_id),
        )
        await c.execute(
            """UPDATE runs SET status=%s,phase=%s,lease_owner=NULL,lease_until=NULL,
            deadline=now()+%s*interval '1 second',attempts=0,
            finished_at=CASE WHEN %s THEN now() ELSE NULL END WHERE id=%s""",
            (
                "queued" if wanted == "approved" else "needs_human",
                "execute",
                cfg.run_timeout_seconds,
                wanted == "rejected",
                run["id"],
            ),
        )
        if wanted == "rejected":
            result = {
                **run["result"],
                "disposition": "needs_human",
                "summary": "The proposed repair was declined. No operation was executed; human review is required.",
                "reply": "We reviewed the account issue and have escalated it for further investigation. No repair or additional charge was made.",
            }
            await c.execute("UPDATE runs SET result=%s WHERE id=%s", (js(result), run["id"]))
            await c.execute(
                "UPDATE tickets SET status='needs_human' WHERE id=%s AND tenant_id=%s",
                (run["ticket_id"], actor["tenant_id"]),
            )
    await db.event(
        run,
        "approval",
        "Repair approved" if wanted == "approved" else "Repair rejected",
        {"action_id": str(action_id), "decision": wanted},
    )
    await db.audit(actor["tenant_id"], actor["id"], "action." + wanted, action_id, run["id"])
    return {"status": wanted, "run_id": action["run_id"]}


@app.patch("/api/runs/{run_id}/draft")
async def draft(run_id: UUID, body: Draft, request: Request, actor=Depends(identity)):
    db = request.app.state.db
    async with db.pool.connection() as c, c.transaction():
        row = await (
            await c.execute(
                "SELECT status,result FROM runs WHERE id=%s AND tenant_id=%s FOR UPDATE",
                (run_id, actor["tenant_id"]),
            )
        ).fetchone()
        if not row:
            raise HTTPException(404, "Run not found")
        if row["status"] in ("queued", "running") or "reply" not in row["result"]:
            raise HTTPException(409, "Wait for investigation findings before editing the reply")
        await c.execute(
            "UPDATE runs SET result=jsonb_set(result,'{reply}',%s) WHERE id=%s AND tenant_id=%s",
            (js(body.reply), run_id, actor["tenant_id"]),
        )
    return {"saved": True}


@app.get("/api/documents/{document_id}")
async def document(document_id: UUID, request: Request, actor=Depends(identity)):
    row = await request.app.state.db.one(
        "SELECT id,source_key,title,version,product_version,body FROM documents WHERE id=%s AND tenant_id=%s",
        (document_id, actor["tenant_id"]),
    )
    if not row:
        raise HTTPException(404, "Document not found")
    return row


@app.get("/api/metrics")
async def metrics(request: Request, actor=Depends(identity)):
    db = request.app.state.db
    counts = await db.all(
        "SELECT status,count(*) AS count FROM runs WHERE tenant_id=%s GROUP BY status", (actor["tenant_id"],)
    )
    usage = await db.one(
        """SELECT count(*) AS calls,coalesce(sum(input_tokens+output_tokens),0) AS tokens,
        sum(cost) AS reported_cost,round(avg(duration_ms)) AS average_latency_ms
        FROM model_calls m JOIN runs r ON r.id=m.run_id WHERE r.tenant_id=%s""",
        (actor["tenant_id"],),
    )
    audit = await db.all(
        "SELECT verb,object_id,trace_id,created_at FROM audit WHERE tenant_id=%s ORDER BY id DESC LIMIT 50",
        (actor["tenant_id"],),
    )
    return {"runs": counts, "usage": usage, "audit": audit}


class ToolCall(Strict):
    name: str
    arguments: dict


@app.post("/api/internal/tools")
async def internal(body: ToolCall, request: Request, authorization: str = Header(default="")):
    context = read_delegation(authorization.removeprefix("Bearer "))
    run = await request.app.state.db.one(
        """SELECT r.* FROM runs r JOIN actors a ON a.id=r.actor_id AND a.tenant_id=r.tenant_id
        WHERE r.id=%s AND r.tenant_id=%s AND r.actor_id=%s AND r.lease_owner=%s
        AND r.lease_until>now() AND r.status='running' AND NOT r.cancel_requested""",
        (context["run"], context["tenant"], context["actor"], context["lease"]),
    )
    if not run:
        raise HTTPException(404, "Run context not found")
    return await request.app.state.tools.call(run, body.name, body.arguments, "mcp")


dist = ROOT / "frontend" / "dist"
if (dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")


@app.get("/")
async def index():
    if (dist / "index.html").exists():
        return FileResponse(dist / "index.html")
    return {"app": "S(AI)pport", "ui": "Run the frontend development server on port 5173."}
