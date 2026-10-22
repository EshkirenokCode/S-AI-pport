import hashlib
import json
from datetime import UTC, datetime


class PolicyError(ValueError):
    pass


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def eligible(state, kind, target):
    if kind == "reprocess_billing_event":
        billing = state["billing"]
        event = billing["event"]
        if (
            billing["payment_status"] != "succeeded"
            or billing["expected_plan"] != "Pro"
            or state["plan"] != "Free"
            or not event
            or event["id"] != target
            or event["status"] != "failed"
            or not event["retryable"]
            or event["error"] not in ("503", "timeout")
        ):
            raise PolicyError("Billing preconditions are not satisfied; escalate for review.")
    elif kind == "retry_delivery":
        delivery = state["delivery"]
        event = delivery["event"]
        if (
            delivery["integration_status"] != "active"
            or not delivery["configuration_valid"]
            or not event
            or event["id"] != target
            or event["status"] != "failed"
            or not event["retryable"]
            or event["error"] not in ("429", "503", "timeout")
        ):
            raise PolicyError("Delivery is not eligible for a safe retry; escalate for review.")
        if datetime.fromisoformat(event["retry_after"].replace("Z", "+00:00")) > datetime.now(UTC):
            raise PolicyError("Destination cooldown has not elapsed.")
    else:
        raise PolicyError("Unknown action.")


def proposal(state, kind, target):
    eligible(state, kind, target)
    return {
        "kind": kind,
        "target_id": target,
        "account_id": state["id"],
        "expected_version": state["version"],
        "expected_effect": "Activate the paid Pro entitlement; no charge."
        if kind == "reprocess_billing_event"
        else "Retry this delivery once and verify destination acknowledgement.",
    }
