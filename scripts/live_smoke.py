"""Explicit live-model smoke test. Uses only the adapter's zero-price routes."""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx


def wait(client, run_id):
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        run = client.get("/api/runs/" + run_id).json()
        if run["status"] not in ("queued", "running"):
            return run
        time.sleep(1)
    raise TimeoutError("Run did not reach a stable state")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="evals/reports/live-smoke.json")
    parser.add_argument(
        "--families", nargs="+", default=["billing", "integration", "configuration"]
    )
    args = parser.parse_args()
    report = {
        "kind": "live_smoke",
        "date": datetime.now(UTC).isoformat(),
        "prompt_version": "support-v1",
        "dataset": "three canonical synthetic cases; no accuracy claim",
        "cases": [],
    }
    with httpx.Client(base_url=args.url, timeout=30) as client:
        client.post("/api/demo/session", json={}).raise_for_status()
        tickets = client.get("/api/tickets").json()
        for family in args.families:
            ticket = next(t for t in tickets if t["family"] == family)
            started = time.monotonic()
            response = client.post(
                "/api/tickets/" + ticket["id"] + "/runs",
                json={"provider": "openrouter"},
            )
            response.raise_for_status()
            run = wait(client, response.json()["id"])
            proposal_status = run["status"]
            if run["status"] == "waiting_for_approval":
                action = run["actions"][0]
                client.post(
                    "/api/actions/" + action["id"] + "/decision",
                    json={"decision": "approve", "digest": action["digest"]},
                ).raise_for_status()
                run = wait(client, run["id"])
            item = {
                "family": family,
                "run_id": run["id"],
                "proposal_status": proposal_status,
                "status": run["status"],
                "verification": run["result"].get("verification"),
                "source_count": len(run["result"].get("source_ids", [])),
                "error": run["error"],
                "model_calls": run["usage"],
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "mcp_used": any(e["kind"] == "transport" for e in run["events"]),
                "tool_errors": [
                    e["data"]["result"].get("error")
                    for e in run["events"]
                    if e["kind"] == "tool_error"
                ],
            }
            report["cases"].append(item)
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2) + "\n")
            print(
                f"{family}: {run['status']}; model calls={len(run['usage'])}",
                flush=True,
            )
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
