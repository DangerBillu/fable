from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from runtime.state import DomElement


@dataclass
class TelemetryExtractor:
    """Extract safe telemetry from already-sanitized text and DOM labels."""

    confidence: float = 0.9

    def extract(self, visible_text: str, elements: tuple[DomElement, ...]) -> tuple[dict[str, Any], dict[str, Any]]:
        timestamp = datetime.now(timezone.utc).isoformat()
        text = self._combined_text(visible_text, elements)
        telemetry: dict[str, Any] = {}

        self._number(telemetry, "altitude_km", text, r"\baltitude\b[^-\d]{0,24}(-?\d+(?:\.\d+)?)\s*(km|kilometers?|m|meters?)", timestamp, {"m": 0.001, "meter": 0.001, "meters": 0.001})
        self._number(telemetry, "velocity_km_s", text, r"\bvelocity\b[^-\d]{0,24}(-?\d+(?:\.\d+)?)\s*(km/s|km\s*per\s*s|m/s|m\s*per\s*s)", timestamp, {"m/s": 0.001, "m per s": 0.001})
        self._number(telemetry, "wind_m_s", text, r"\bwind\b[^-\d]{0,24}(-?\d+(?:\.\d+)?)\s*(m/s|m\s*per\s*s|km/h|kph)", timestamp, {"km/h": 0.277777778, "kph": 0.277777778})
        self._number(telemetry, "fuel_percent", text, r"\bfuel\b[^-\d]{0,24}(-?\d+(?:\.\d+)?)\s*(%|percent)?", timestamp)
        self._number(telemetry, "temperature_c", text, r"\b(?:temperature|temp)\b[^-\d]{0,24}(-?\d+(?:\.\d+)?)\s*(c|°c|f|°f)?", timestamp, {"f": lambda value: (value - 32) * 5 / 9, "°f": lambda value: (value - 32) * 5 / 9})
        self._number(telemetry, "acceleration_m_s2", text, r"\bacceleration\b[^-\d]{0,24}(-?\d+(?:\.\d+)?)\s*(m/s2|m/s\^2|g)?", timestamp, {"g": 9.80665})

        ui_state: dict[str, Any] = {}
        status_match = re.search(r"\b(?:status|state)\b[^\w]{0,12}(running|paused|hold|aborted|complete|nominal|warning|critical)", text, re.I)
        if status_match:
            ui_state["simulation_state"] = status_match.group(1).lower()
        elif re.search(r"\brunning\b", text, re.I):
            ui_state["simulation_state"] = "running"

        return telemetry, ui_state

    def _combined_text(self, visible_text: str, elements: tuple[DomElement, ...]) -> str:
        labels = []
        for element in elements:
            labels.extend(part for part in (element.aria_label, element.text, element.placeholder) if part)
        return "\n".join([visible_text, *labels])

    def _number(
        self,
        telemetry: dict[str, Any],
        key: str,
        text: str,
        pattern: str,
        timestamp: str,
        conversions: dict[str, float | Any] | None = None,
    ) -> None:
        match = re.search(pattern, text, re.I)
        if not match:
            return
        value = float(match.group(1))
        unit = (match.group(2) or "").lower().replace("  ", " ") if match.lastindex and match.lastindex >= 2 else ""
        conversion = (conversions or {}).get(unit)
        if callable(conversion):
            value = float(conversion(value))
        elif conversion:
            value *= float(conversion)
        telemetry[key] = {
            "value": round(value, 4),
            "confidence": self.confidence,
            "timestamp": timestamp,
            "source": "sanitized_text",
        }
