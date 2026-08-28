from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from runtime.state import SanitizedState


@dataclass
class TemporalDiffEngine:
    latest_by_session: dict[str, SanitizedState] = field(default_factory=dict)

    def update(self, session_id: str, current: SanitizedState) -> dict[str, Any]:
        previous = self.latest_by_session.get(session_id)
        self.latest_by_session[session_id] = current
        if previous is None:
            return {
                "event": "initial_observation",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "changed": current.telemetry,
                "stale": [],
            }

        changed: dict[str, Any] = {}
        for key, current_value in current.telemetry.items():
            previous_value = previous.telemetry.get(key)
            if self._value(previous_value) != self._value(current_value):
                changed[key] = {"previous": self._value(previous_value), "current": self._value(current_value)}

        stale = sorted(set(previous.telemetry) - set(current.telemetry))
        return {
            "event": "telemetry_update" if changed or stale else "no_meaningful_change",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "changed": changed,
            "stale": stale,
        }

    def _value(self, field: Any) -> Any:
        if isinstance(field, dict):
            return field.get("value")
        return field
