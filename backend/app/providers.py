import json
import time
from pathlib import Path
from uuid import uuid4

import httpx

from app.policy import PolicyError, eligible
from app.schemas import model_tools
from app.services import rate_limit
from app.settings import settings

PROMPT_VERSION = "support-v1.1"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.txt").read_text()


def tool_call(name, args):
    return {
        "id": "call_" + uuid4().hex,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def offline_next(ticket, messages):
    """Deterministic contract driver; decisions depend on actual tool observations."""
    calls, results = {}, {}
    for message in messages:
        if message["role"] == "assistant":
            for c in message.get("tool_calls", []):
                calls[c["id"]] = c["function"]["name"]
        if message["role"] == "tool":
            results[calls[message["tool_call_id"]]] = json.loads(message["content"])
    family = ticket["family"]
    if "get_account_context" not in results:
        return [tool_call("get_account_context", {})]
    relevant = "get_billing_state" if family == "billing" else "get_delivery_state"
    if family != "configuration" and relevant not in results:
        return [tool_call(relevant, {})]
    if "search_documentation" not in results:
        query = {
            "billing": "paid subscription",
            "integration": "webhook deliveries",
            "configuration": "webhook retries",
        }[family]
        return [tool_call("search_documentation", {"query": query})]
    docs = results["search_documentation"].get("documents", [])
    if docs and "read_document" not in results:
        return [tool_call("read_document", {"document_id": str(docs[0]["id"])})]
    sources = [r["evidence_id"] for r in results.values() if "evidence_id" in r and "error" not in r]
    if docs:
        sources.append(str(docs[0]["id"]))
    account = results["get_account_context"]
    disposition, summary, facts, missing = (
        "needs_human",
        "The available evidence requires a human review.",
        [],
        [],
    )
    reply = "I checked the available account information. A support operator needs to review the evidence before we proceed."
    if family != "configuration":
        state = {"id": account.get("id"), "plan": account.get("plan"), "version": account.get("version")}
        key = "billing" if family == "billing" else "delivery"
        state[key] = results[relevant].get(key, {})
        event = state[key].get("event")
        kind = "reprocess_billing_event" if family == "billing" else "retry_delivery"
        facts = [f"Current plan: {state['plan']}."]
        if family == "billing":
            facts.append(f"Payment status: {state[key].get('payment_status', 'unknown')}.")
        if event:
            facts.append(f"Event {event['id']}: {event['status']}; last error: {event.get('error', 'none')}.")
        try:
            if not docs or not event:
                raise PolicyError("An event or applicable procedure is missing.")
            eligible(state, kind, event["id"])
            if "propose_action" not in results:
                return [tool_call("propose_action", {"kind": kind, "target_id": event["id"]})]
            if "proposal" in results["propose_action"]:
                disposition = "propose_action"
                summary = (
                    "The payment succeeded, but a transient billing event failure left access on Free."
                    if family == "billing"
                    else "A transient delivery failure left this event undelivered. The cooldown has elapsed."
                )
                reply = (
                    "I confirmed the payment and found a failed access update. A safe reprocessing operation is awaiting operator approval; it will not charge you again."
                    if family == "billing"
                    else "I found a transient delivery failure. One retry is awaiting operator approval. We will check the destination acknowledgement afterward."
                )
            else:
                missing.append(results["propose_action"].get("error", "Proposal rejected"))
        except (PolicyError, KeyError) as e:
            if (
                family == "billing"
                and state.get("plan") == "Pro"
                and event
                and event["status"] == "processed"
            ):
                disposition, summary = (
                    "resolved",
                    "The paid Pro entitlement is already active and the event was processed.",
                )
                reply = "I verified that your Pro access is active and the payment event has already been processed. No repair or additional charge is needed."
            else:
                missing.append(str(e))
                summary = "The evidence does not satisfy the repair preconditions. Human review is required."
    elif "regional event mirroring" in ticket["body"].lower():
        disposition, summary = (
            "clarify",
            "The current documentation does not define a regional event mirroring setting.",
        )
        missing = ["Confirm the intended feature and supported product configuration with the product team."]
        reply = "I could not find a supported regional event mirroring setting in the current documentation. Could you describe the destination and outcome you need?"
    elif docs:
        disposition, summary = (
            "resolved",
            "The current 2.4 documentation explains the retry settings and supported response types.",
        )
        facts = [
            "Product version: 2.4.",
            "Retry attempts: 0–3; default 3.",
            "Retryable failures: 429, 503, and network timeouts.",
        ]
        reply = "In version 2.4, open Settings → Integrations → Webhooks, select your endpoint, then Delivery policy. Set Retry attempts from 0 to 3 (default 3), save, and send a test event. Retries use 30 seconds, 2 minutes, and 10 minutes; 429 respects Retry-After. Correct credentials for 401/403 instead of retrying."
    return [
        tool_call(
            "finish_investigation",
            {
                "disposition": disposition,
                "summary": summary,
                "facts": facts,
                "missing_information": missing,
                "source_ids": list(dict.fromkeys(sources)),
                "reply": reply,
            },
        )
    ]


async def live_next(db, run, messages):
    cfg = settings()
    model = cfg.openrouter_model
    spent = await db.one(
        "SELECT count(*) AS calls,coalesce(sum(input_tokens+output_tokens),0) AS tokens FROM model_calls WHERE run_id=%s",
        (run["id"],),
    )
    if spent["calls"] >= cfg.max_model_calls or spent["tokens"] >= cfg.max_model_tokens:
        raise PolicyError("Persisted model call/token budget exhausted")
    if model != "openrouter/free" and not model.endswith(":free"):
        raise PolicyError("Only free OpenRouter models are allowed; no paid fallback is configured.")
    await rate_limit(db, "live_calls:global", cfg.live_calls_per_day, 86400)
    started = time.monotonic()
    async with httpx.AsyncClient(timeout=httpx.Timeout(65, connect=10)) as client:
        catalog = await client.get("https://openrouter.ai/api/v1/models")
        catalog.raise_for_status()
        row = next((m for m in catalog.json()["data"] if m["id"] == model), None)
        if not row or any(float(row["pricing"].get(k, "1")) != 0 for k in ("prompt", "completion")):
            raise PolicyError("Selected model is not currently listed with zero input and output price.")
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": "Bearer " + cfg.openrouter_api_key.get_secret_value(),
                "X-Title": "S(AI)pport",
            },
            json={
                "model": model,
                "messages": messages,
                "tools": model_tools(),
                "tool_choice": "auto",
                "temperature": 0.1,
                "max_tokens": 2200,
                "provider": {"require_parameters": True, "max_price": {"prompt": 0, "completion": 0}},
            },
        )
        response.raise_for_status()
        data = response.json()
    if "error" in data or not data.get("choices"):
        raise PolicyError("Provider returned an invalid completion")
    usage = data.get("usage", {})
    await db.execute(
        "INSERT INTO model_calls(run_id,model,input_tokens,output_tokens,cost,duration_ms) VALUES(%s,%s,%s,%s,%s,%s)",
        (
            run["id"],
            data.get("model", model),
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
            usage.get("cost"),
            int((time.monotonic() - started) * 1000),
        ),
    )
    await db.execute("UPDATE runs SET model=%s WHERE id=%s", (data.get("model", model), run["id"]))
    # Provider reasoning fields and text are deliberately excluded from persisted/public events.
    return data["choices"][0]["message"].get("tool_calls", [])
