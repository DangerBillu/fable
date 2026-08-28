from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from runtime.state import ApprovedAction, BrowserAction, PolicyDecision
from runtime.tokenization import TokenVault


@dataclass
class McpTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]


class McpRegistry:
    """Central registry for all J.A.R.V.I.S. MCP tool servers."""

    def __init__(self, vault: TokenVault) -> None:
        self.vault = vault
        self._tools: dict[str, McpTool] = {}
        self._register_default_tools()

    def register(self, tool: McpTool) -> None:
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> McpTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in self._tools.values()
        ]

    def _register_default_tools(self) -> None:
        # 1. Flight Actuator Tools (Browser Pilot)
        self.register(
            McpTool(
                name="flight.trigger_stage_separation",
                description="Triggers stage 1 booster separation on the rocket flight console.",
                parameters={"type": "object", "properties": {"reason": {"type": "string"}}},
                handler=lambda **kw: {"action": "click", "element_id": "btn-stage-sep", "status": "executed"},
            )
        )
        self.register(
            McpTool(
                name="flight.jettison_fairing",
                description="Jettisons the payload fairing (ogive) once above atmospheric ceiling.",
                parameters={"type": "object", "properties": {"altitude_km": {"type": "number"}}},
                handler=lambda **kw: {"action": "click", "element_id": "btn-fairing-jettison", "status": "executed"},
            )
        )
        self.register(
            McpTool(
                name="flight.recalibrate_gimbal",
                description="Trims and recalibrates the rocket engine nozzle gimbal angle.",
                parameters={"type": "object", "properties": {"pitch_delta": {"type": "number"}}},
                handler=lambda **kw: {"action": "click", "element_id": "btn-gimbal-recal", "status": "executed"},
            )
        )
        self.register(
            McpTool(
                name="flight.emergency_hold",
                description="Freezes launch telemetry stream for immediate security or safety audit.",
                parameters={"type": "object", "properties": {}},
                handler=lambda **kw: {"action": "click", "element_id": "btn-telemetry-hold", "status": "executed"},
            )
        )

        # 2. Comms Dispatch Tools
        self.register(
            McpTool(
                name="comms.transmit_telemetry_email",
                description="Encrypted email dispatch of sanitized flight telemetry to mission authorities.",
                parameters={
                    "type": "object",
                    "properties": {
                        "recipient": {"type": "string"},
                        "subject": {"type": "string"},
                        "sanitized_body": {"type": "string"},
                    },
                    "required": ["recipient"],
                },
                handler=self._handle_comms_email,
            )
        )

        # 3. Telemetry Analyst Tools
        self.register(
            McpTool(
                name="telemetry.analyze_flight_safety",
                description="Evaluates live flight telemetry for Max-Q pressure, wind shear, and stage separation criteria.",
                parameters={
                    "type": "object",
                    "properties": {
                        "altitude_km": {"type": "number"},
                        "velocity_ms": {"type": "number"},
                        "dynamic_pressure_kpa": {"type": "number"},
                    },
                },
                handler=self._handle_telemetry_analysis,
            )
        )

    def _handle_comms_email(self, recipient: str = "mission-control@isro.gov.in", subject: str = "", sanitized_body: str = "", **kw) -> dict:
        resolved_recipient = self.vault.resolve(recipient) if self.vault.has(recipient) else recipient
        return {
            "action": "click",
            "element_id": "btn-send-telemetry-report",
            "recipient": resolved_recipient,
            "subject": subject or "LVM3-M4 Launch Telemetry & Max-Q Stage Report",
            "status": "queued_for_transmission",
        }

    def _handle_telemetry_analysis(self, altitude_km: float = 54.2, velocity_ms: float = 1824.5, dynamic_pressure_kpa: float = 34.8, **kw) -> dict:
        is_max_q_cleared = dynamic_pressure_kpa < 40.0
        is_staging_ready = altitude_km >= 50.0
        return {
            "max_q_cleared": is_max_q_cleared,
            "staging_ready": is_staging_ready,
            "recommended_action": "flight.trigger_stage_separation" if is_staging_ready else "monitor",
            "status": "nominal",
        }
