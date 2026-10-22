import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import jwt
from fastapi import HTTPException, Request

from app.fixtures import DOCUMENTS, SCENARIOS
from app.settings import settings


class LabClient:
    def __init__(self):
        cfg = settings()
        self.client = httpx.AsyncClient(
            base_url=cfg.sandbox_url,
            timeout=8,
            headers={"Authorization": "Bearer " + cfg.sandbox_token.get_secret_value()},
        )

    async def close(self):
        await self.client.aclose()

    async def get(self, path):
        for attempt in range(3):
            try:
                response = await self.client.get(path)
                if response.status_code not in (429, 502, 503, 504) or attempt == 2:
                    response.raise_for_status()
                    return response.json()
            except httpx.TransportError:
                if attempt == 2:
                    raise
            await asyncio.sleep(0.15 * 2**attempt)

    async def state(self, tenant, account):
        return await self.get(f"/tenants/{tenant}/accounts/{account}")

    async def receipt(self, tenant, operation):
        try:
            return await self.get(f"/tenants/{tenant}/operations/{operation}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise


async def rate_limit(db, bucket, limit, seconds=3600):
    row = await db.one(
        """INSERT INTO rate_limits(bucket,count,expires_at) VALUES(%s,1,now() + %s * interval '1 second')
        ON CONFLICT(bucket) DO UPDATE SET count=CASE WHEN rate_limits.expires_at < now() THEN 1 ELSE rate_limits.count+1 END,
        expires_at=CASE WHEN rate_limits.expires_at < now() THEN excluded.expires_at ELSE rate_limits.expires_at END
        RETURNING count""",
        (bucket, seconds),
    )
    if row["count"] > limit:
        raise HTTPException(429, "Workspace quota reached. Try again later.")


async def identity(request: Request):
    token = request.cookies.get("saipport_session", "")
    if not token:
        raise HTTPException(401, "Create a demo workspace to continue")
    hashed = hashlib.sha256(token.encode()).hexdigest()
    actor = await request.app.state.db.one(
        """SELECT a.*,t.name AS tenant_name FROM sessions s
        JOIN actors a ON a.id=s.actor_id AND a.tenant_id=s.tenant_id JOIN tenants t ON t.id=s.tenant_id
        WHERE s.token_hash=%s AND s.expires_at>now()""",
        (hashed,),
    )
    if not actor:
        raise HTTPException(401, "Session expired. Create a new workspace.")
    return actor


def delegate(run):
    return jwt.encode(
        {
            "scope": "tools",
            "run": str(run["id"]),
            "tenant": str(run["tenant_id"]),
            "actor": str(run["actor_id"]),
            "exp": datetime.now(UTC) + timedelta(seconds=settings().run_timeout_seconds + 30),
        },
        settings().app_secret.get_secret_value(),
        algorithm="HS256",
    )


def read_delegation(token):
    try:
        result = jwt.decode(
            token,
            settings().app_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["scope", "run", "tenant", "actor", "exp"]},
        )
        if result["scope"] != "tools":
            raise ValueError("Invalid scope")
        return result
    except (jwt.PyJWTError, ValueError) as e:
        raise HTTPException(401, "Invalid delegated context") from e


async def create_workspace(db, lab, role):
    tenant, actor = uuid4(), uuid4()
    token = secrets.token_urlsafe(40)
    accounts = []
    async with db.pool.connection() as c, c.transaction():
        await c.execute("INSERT INTO tenants(id,name) VALUES(%s,%s)", (tenant, "Acme Support"))
        await c.execute(
            "INSERT INTO actors(id,tenant_id,name,role) VALUES(%s,%s,%s,%s)",
            (actor, tenant, "Demo Operator" if role == "operator" else "Demo Analyst", role),
        )
        for i, (family, scenario, subject, body, customer, company, priority) in enumerate(SCENARIOS):
            aid = uuid4()
            accounts.append({"id": str(aid), "scenario": scenario, "company": company})
            await c.execute(
                """INSERT INTO tickets(id,tenant_id,number,family,subject,body,customer,email,
                account_id,scenario,priority) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    uuid4(),
                    tenant,
                    1042 + i,
                    family,
                    subject,
                    body,
                    customer,
                    customer.lower().replace(" ", ".") + "@example.test",
                    aid,
                    scenario,
                    priority,
                ),
            )
        for key, title, version, product, body in DOCUMENTS:
            await c.execute(
                "INSERT INTO documents(id,tenant_id,source_key,title,version,product_version,body) VALUES(%s,%s,%s,%s,%s,%s,%s)",
                (uuid4(), tenant, key, title, version, product, body),
            )
        response = await lab.client.post("/seed", json={"tenant_id": str(tenant), "accounts": accounts})
        response.raise_for_status()
        await c.execute(
            "INSERT INTO sessions(token_hash,tenant_id,actor_id,expires_at) VALUES(%s,%s,%s,now()+%s*interval '1 hour')",
            (hashlib.sha256(token.encode()).hexdigest(), tenant, actor, settings().session_hours),
        )
    return token, tenant
