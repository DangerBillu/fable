from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.state import ActionRequest, SanitizedObservation


ALLOWED_ACTIONS = {
    "browser.get_page",
    "browser.get_dom",
    "browser.get_screenshot",
    "browser.click",
    "browser.type",
    "browser.scroll",
    "browser.press_key",
    "browser.navigate",
    "browser.select",
    "browser.go_back",
    "browser.wait",
    "browser.done",
}


def observation_to_json(observation: SanitizedObservation, capture_id: str | None = None) -> dict[str, Any]:
    payload = {
        "schema_version": "1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": {
            "application": observation.sanitized_dom.domain,
            "capture_id": capture_id or observation.session_id,
        },
        "telemetry": observation.state.telemetry,
        "ui_state": observation.state.ui_state,
        "safe_text": [observation.sanitized_dom.visible_text] if observation.sanitized_dom.visible_text else [],
        "redactions": [
            {
                "type": region.category.value.lower(),
                "bbox": list(region.bbox),
                "confidence": region.confidence,
            }
            for region in observation.sensitive_regions
        ],
    }
    validate_observation_json(payload)
    return payload


def action_request_to_json(request: ActionRequest) -> dict[str, Any]:
    parameters: dict[str, Any] = {}
    for name in ("element_id", "text", "url", "key", "value", "delta_x", "delta_y"):
        value = getattr(request, name)
        if value is not None:
            parameters[name] = value
    payload = {
        "action_id": str(uuid4()),
        "action": request.action.value,
        "parameters": parameters,
        "reason": request.reasoning,
    }
    validate_action_json(payload)
    return payload


def validate_observation_json(payload: dict[str, Any]) -> None:
    required = {"schema_version", "timestamp", "source", "telemetry", "ui_state", "safe_text", "redactions"}
    missing = required - set(payload)
    if missing:
        raise ValueError(f"Observation JSON missing required fields: {sorted(missing)}")
    if payload["schema_version"] != "1.0":
        raise ValueError("Unsupported observation schema version")
    if not isinstance(payload["telemetry"], dict) or not isinstance(payload["ui_state"], dict):
        raise TypeError("Observation telemetry and ui_state must be objects")
    if not isinstance(payload["safe_text"], list) or not isinstance(payload["redactions"], list):
        raise TypeError("Observation safe_text and redactions must be arrays")


def validate_action_json(payload: dict[str, Any]) -> None:
    required = {"action_id", "action", "parameters", "reason"}
    missing = required - set(payload)
    if missing:
        raise ValueError(f"Action JSON missing required fields: {sorted(missing)}")
    if payload["action"] not in ALLOWED_ACTIONS:
        raise ValueError(f"Action is not allowlisted: {payload['action']}")
    if not isinstance(payload["parameters"], dict):
        raise TypeError("Action parameters must be an object")
