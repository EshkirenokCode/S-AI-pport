"""Verify billing through the externally reachable API of a Compose stack."""

import argparse
import time

import httpx


def wait(client, run_id):
    for _ in range(150):
        response = client.get("/api/runs/" + run_id)
        response.raise_for_status()
        run = response.json()
        if run["status"] not in ("queued", "running"):
            return run
        time.sleep(0.2)
    raise TimeoutError("Container workflow did not finish")


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", default="http://127.0.0.1:8000")
args = parser.parse_args()

with httpx.Client(base_url=args.base_url, timeout=20) as client:
    client.post("/api/demo/session", json={}).raise_for_status()
    ticket = client.get("/api/tickets").json()[0]
    r = client.post(
        "/api/tickets/" + ticket["id"] + "/runs", json={"provider": "deterministic"}
    )
    r.raise_for_status()
    run = wait(client, r.json()["id"])
    assert run["status"] == "waiting_for_approval", run
    action = run["actions"][0]
    client.post(
        "/api/actions/" + action["id"] + "/decision",
        json={"decision": "approve", "digest": action["digest"]},
    ).raise_for_status()
    run = wait(client, run["id"])
    assert run["status"] == "completed", run
    assert run["result"]["verification"]["verified"]
    print("Compose billing workflow: approved, executed, and verified.")
