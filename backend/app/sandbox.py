import hmac
from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import Field

from app.db import Database, js
from app.fixtures import account_state
from app.policy import PolicyError, digest, eligible
from app.schemas import Strict
from app.settings import settings

cfg = settings()
db = Database(cfg.sandbox_database_url)


@asynccontextmanager
async def lifespan(app):
    await db.open()
    yield
    await db.close()


async def trusted(authorization: str = Header(default="")):
    if not hmac.compare_digest(authorization, "Bearer " + cfg.sandbox_token.get_secret_value()):
        raise HTTPException(401, "Service authentication required")


app = FastAPI(title="Synthetic SaaS laboratory", lifespan=lifespan, dependencies=[Depends(trusted)])


class Seed(Strict):
    tenant_id: UUID
    accounts: list[dict] = Field(max_length=30)


class Operation(Strict):
    operation_id: UUID
    tenant_id: UUID
    account_id: UUID
    kind: str
    target_id: str
    expected_version: int


@app.get("/health", dependencies=[])
async def health():
    return {"status": "ok", "synthetic": True}


@app.post("/seed")
async def seed(body: Seed):
    async with db.pool.connection() as c, c.transaction():
        for a in body.accounts:
            state = account_state(a["id"], body.tenant_id, a["scenario"], a["company"])
            await c.execute(
                "INSERT INTO accounts(id,tenant_id,state) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
                (a["id"], body.tenant_id, js(state)),
            )
    return {"seeded": len(body.accounts)}


@app.get("/tenants/{tenant}/accounts/{account}")
async def account(tenant: UUID, account: UUID):
    row = await db.one("SELECT state,version FROM accounts WHERE id=%s AND tenant_id=%s", (account, tenant))
    if not row:
        raise HTTPException(404, "Account not found")
    state = row["state"]
    # Fixture controls stay server-side; they are not evidence for an investigator.
    state.pop("scenario", None)
    return {**state, "version": row["version"]}


@app.get("/tenants/{tenant}/operations/{operation}")
async def receipt(tenant: UUID, operation: UUID):
    row = await db.one(
        "SELECT result FROM receipts WHERE operation_id=%s AND tenant_id=%s", (operation, tenant)
    )
    if not row:
        raise HTTPException(404, "Receipt not found")
    return row["result"]


@app.delete("/tenants/{tenant}")
async def expire_tenant(tenant: UUID):
    async with db.pool.connection() as c, c.transaction():
        await c.execute("DELETE FROM receipts WHERE tenant_id=%s", (tenant,))
        await c.execute("DELETE FROM accounts WHERE tenant_id=%s", (tenant,))
    return {"removed": True}


@app.post("/operations")
async def operate(body: Operation):
    payload_hash = digest(body.model_dump(mode="json"))
    async with db.pool.connection() as c, c.transaction():
        row = await (
            await c.execute(
                "SELECT * FROM accounts WHERE id=%s AND tenant_id=%s FOR UPDATE",
                (body.account_id, body.tenant_id),
            )
        ).fetchone()
        if not row:
            raise HTTPException(404, "Account not found")
        old = await (
            await c.execute("SELECT * FROM receipts WHERE operation_id=%s", (body.operation_id,))
        ).fetchone()
        if old:
            if old["tenant_id"] != body.tenant_id or old["payload_hash"] != payload_hash:
                raise HTTPException(409, "Idempotency key is bound to a different operation")
            return old["result"]
        if row["version"] != body.expected_version:
            raise HTTPException(409, "Account changed after proposal; investigate again")
        state = row["state"]
        try:
            eligible(state, body.kind, body.target_id)
        except PolicyError as e:
            raise HTTPException(409, str(e)) from e
        if body.kind == "reprocess_billing_event":
            state["billing"]["event"]["status"] = "processed"
            state["billing"]["event"]["attempts"].append(
                {"status": "200", "operation_id": str(body.operation_id)}
            )
            if state["scenario"] != "billing_no_effect":
                state["plan"] = "Pro"
        else:
            state["delivery"]["event"]["status"] = "delivered"
            state["delivery"]["event"]["acknowledged"] = True
            state["delivery"]["event"]["attempts"].append(
                {"status": "200", "operation_id": str(body.operation_id)}
            )
        result = {
            "operation_id": str(body.operation_id),
            "applied": True,
            "account_version": row["version"] + 1,
        }
        await c.execute(
            "UPDATE accounts SET state=%s,version=version+1 WHERE id=%s", (js(state), body.account_id)
        )
        await c.execute(
            "INSERT INTO receipts(operation_id,tenant_id,account_id,payload_hash,result) VALUES(%s,%s,%s,%s,%s)",
            (body.operation_id, body.tenant_id, body.account_id, payload_hash, js(result)),
        )
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.sandbox:app", host="127.0.0.1", port=8001)
