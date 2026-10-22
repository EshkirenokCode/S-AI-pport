import time
from uuid import uuid4

from pydantic import ValidationError

from app.db import clean, js
from app.policy import PolicyError, digest, proposal
from app.retrieval import retrieve
from app.schemas import TOOL_SCHEMAS
from app.settings import settings


class ToolRegistry:
    def __init__(self, db, lab):
        self.db, self.lab = db, lab

    async def call(self, run, name, arguments, transport="direct"):
        started = time.monotonic()
        evidence_id = "api:" + str(uuid4())
        try:
            if name not in TOOL_SCHEMAS:
                raise PolicyError("Unknown tool")
            args = TOOL_SCHEMAS[name][0].model_validate(arguments).model_dump(mode="json")
            fresh = await self.db.one(
                "SELECT * FROM runs WHERE id=%s AND tenant_id=%s", (run["id"], run["tenant_id"])
            )
            if (
                not fresh
                or fresh["status"] != "running"
                or fresh["phase"] != "investigate"
                or fresh["cancel_requested"]
            ):
                raise PolicyError("Investigation is no longer active")
            n = await self.db.one(
                "SELECT count(*) AS n FROM events WHERE run_id=%s AND kind IN ('tool','tool_error')",
                (run["id"],),
            )
            if n["n"] >= settings().max_tool_calls:
                raise PolicyError("Tool budget exhausted")
            ticket = await self.db.one(
                "SELECT * FROM tickets WHERE id=%s AND tenant_id=%s", (run["ticket_id"], run["tenant_id"])
            )
            result = await self.invoke(run, ticket, name, args)
            result["evidence_id"] = evidence_id
            kind = "tool"
        except (PolicyError, ValidationError) as e:
            result = {"error": str(e)[:1200], "evidence_id": evidence_id}
            kind = "tool_error"
        await self.db.event(
            run,
            kind,
            name.replace("_", " ").capitalize(),
            {
                "tool": name,
                "arguments": arguments,
                "result": result,
                "transport": transport,
                "duration_ms": int((time.monotonic() - started) * 1000),
            },
        )
        return clean(result)

    async def invoke(self, run, ticket, name, args):
        if name in ("get_account_context", "get_billing_state", "get_delivery_state"):
            state = await self.lab.state(run["tenant_id"], ticket["account_id"])
            if name == "get_account_context":
                return {
                    k: v
                    for k, v in state.items()
                    if k in ("id", "company", "product_version", "plan", "version")
                }
            key = "billing" if name == "get_billing_state" else "delivery"
            return {key: state[key], "plan": state["plan"], "account_version": state["version"]}
        if name == "search_documentation":
            state = await self.lab.state(run["tenant_id"], ticket["account_id"])
            rows = await retrieve(
                self.db, run["tenant_id"], state["product_version"], args["query"], ticket["family"]
            )
            return {
                "documents": [{**r, "source_id": str(r["id"]), "excerpt": r["body"][:1100]} for r in rows],
                "retrieval": "postgresql_fts_topic_or_v2",
            }
        if name == "read_document":
            row = await self.db.one(
                "SELECT id,source_key,title,version,product_version,body FROM documents WHERE id=%s AND tenant_id=%s",
                (args["document_id"], run["tenant_id"]),
            )
            if not row:
                raise PolicyError("Document not found in this workspace")
            state = await self.lab.state(run["tenant_id"], ticket["account_id"])
            if row["product_version"] != state["product_version"]:
                raise PolicyError("Document version does not apply to this account")
            return {"document": {**row, "source_id": str(row["id"])}}
        if name == "propose_action":
            if (
                ticket["family"] == "billing"
                and args["kind"] != "reprocess_billing_event"
                or ticket["family"] == "integration"
                and args["kind"] != "retry_delivery"
                or ticket["family"] == "configuration"
            ):
                raise PolicyError("Action does not match ticket family")
            events = await self.db.all(
                "SELECT data FROM events WHERE run_id=%s AND kind='tool'", (run["id"],)
            )
            used = {e["data"]["tool"] for e in events}
            needed = {
                "get_account_context",
                "get_billing_state" if ticket["family"] == "billing" else "get_delivery_state",
                "read_document",
            }
            if not needed.issubset(used):
                raise PolicyError(
                    "Read account, relevant API state, and the exact procedure before proposing"
                )
            expected = "billing-recovery" if ticket["family"] == "billing" else "delivery-recovery"
            docs = [
                e["data"]["result"].get("document", {})
                for e in events
                if e["data"]["tool"] == "read_document"
            ]
            if not any(d.get("source_key") == expected and d.get("product_version") == "2.4" for d in docs):
                raise PolicyError("No applicable procedure has been read")
            state = await self.lab.state(run["tenant_id"], ticket["account_id"])
            payload = proposal(state, args["kind"], args["target_id"])
            action = await self.db.one(
                """INSERT INTO actions(id,tenant_id,run_id,kind,target_id,payload,digest)
                VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(run_id) DO UPDATE SET status=actions.status RETURNING *""",
                (
                    uuid4(),
                    run["tenant_id"],
                    run["id"],
                    args["kind"],
                    args["target_id"],
                    js(payload),
                    digest(payload),
                ),
            )
            return {
                "proposal": action,
                "notice": "Proposed only. A human operator must approve; no repair has executed.",
            }
        if name == "finish_investigation":
            events = await self.db.all(
                "SELECT data FROM events WHERE run_id=%s AND kind='tool'", (run["id"],)
            )
            known = set()
            for event in events:
                result = event["data"]["result"]
                known.add(result.get("evidence_id", ""))
                known.update(str(d["id"]) for d in result.get("documents", []))
                if result.get("document"):
                    known.add(str(result["document"]["id"]))
            if not set(args["source_ids"]).issubset(known):
                raise PolicyError("Unknown evidence reference; cite IDs returned by tools")
            action = await self.db.one(
                "SELECT * FROM actions WHERE run_id=%s AND tenant_id=%s", (run["id"], run["tenant_id"])
            )
            if action and args["disposition"] != "propose_action":
                raise PolicyError(
                    "A proposed repair is pending, not resolved. Use propose_action disposition."
                )
            if args["disposition"] == "propose_action" and not action:
                raise PolicyError("No eligible proposal exists")
            if args["disposition"] in ("resolved", "propose_action") and not args["source_ids"]:
                raise PolicyError("Evidence is required for this disposition")
            if args["disposition"] == "resolved":
                state = await self.lab.state(run["tenant_id"], ticket["account_id"])
                if ticket["family"] == "billing" and not (
                    state["plan"] == "Pro"
                    and state["billing"]["event"]
                    and state["billing"]["event"]["status"] == "processed"
                ):
                    raise PolicyError("Current API state does not establish a resolved billing issue")
                if ticket["family"] == "integration" and state["delivery"]["event"]["status"] != "delivered":
                    raise PolicyError("Delivery is not confirmed; do not claim resolution")
                if ticket["family"] == "configuration" and not any(
                    e["data"]["tool"] == "read_document" for e in events
                ):
                    raise PolicyError("A configuration answer requires an applicable document read")
            await self.db.execute(
                "UPDATE runs SET result=%s WHERE id=%s AND tenant_id=%s",
                (js(args), run["id"], run["tenant_id"]),
            )
            return {"accepted": True, "disposition": args["disposition"]}
        raise PolicyError("Unknown tool")
