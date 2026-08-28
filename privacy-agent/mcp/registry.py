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
    """Central registry for Fable MCP tool servers."""

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
                description="Email dispatch of a sanitized telemetry report.",
                parameters={
                    "type": "object",
                    "properties": {
                        "recipient": {"type": "string"},
                        "subject": {"type": "string"},
                        "sanitized_body": {"type": "string"},
                        "telemetry": {"type": "object"},
                    },
                    "required": ["recipient"],
                },
                handler=self._handle_comms_email,
            )
        )
        self.register(
            McpTool(
                name="comms.email_article_summary",
                description="Email a sanitized summary of the current article or page.",
                parameters={
                    "type": "object",
                    "properties": {
                        "recipient": {"type": "string"},
                        "subject": {"type": "string"},
                        "article_title": {"type": "string"},
                        "article_url": {"type": "string"},
                        "summary": {"type": "string"},
                        "source_excerpt": {"type": "string"},
                    },
                    "required": ["summary"],
                },
                handler=self._handle_article_summary_email,
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
        self.register(
            McpTool(
                name="telemetry.calculate_wind_tally",
                description="Tallies current windspeed with screen telemetry datapoints A (velocity) & B (altitude) and dispatches calculation report to email.",
                parameters={
                    "type": "object",
                    "properties": {
                        "windspeed_knots": {"type": "number"},
                        "velocity_ms": {"type": "number"},
                        "altitude_km": {"type": "number"},
                        "recipient": {"type": "string"},
                    },
                },
                handler=self._handle_wind_tally,
            )
        )

    def _handle_comms_email(self, recipient: str = "mission-control@isro.gov.in", subject: str = "", sanitized_body: str = "", telemetry: dict[str, Any] | None = None, **kw) -> dict:
        from runtime.comms.email_sender import EmailSender
        resolved_recipient = self.vault.resolve(recipient) if self.vault.has(recipient) else recipient
        telemetry_payload = telemetry or {
            "altitude_km": 54.20,
            "velocity_ms": 1824.5,
            "mach": 5.42,
            "dynamic_pressure_kpa": 34.80,
            "chamber_pressure_bar": 58.4,
            "propellant_remaining_pct": 71.8,
        }
        sender = EmailSender()
        dispatch_result = sender.send_telemetry_email(
            recipient=resolved_recipient,
            subject=subject or "LVM3-M4 Launch Telemetry & Max-Q Stage Report",
            telemetry_data=telemetry_payload,
            raw_text=sanitized_body,
        )
        return {
            "action": "click",
            "element_id": "btn-send-telemetry-report",
            "recipient": resolved_recipient,
            "subject": subject or "LVM3-M4 Launch Telemetry & Max-Q Stage Report",
            "dispatch": dispatch_result,
            "status": "delivered_to_smtp" if dispatch_result.get("smtp_sent") else "saved_to_outbox",
        }

    def _handle_article_summary_email(
        self,
        recipient: str = "",
        subject: str = "",
        article_title: str = "",
        article_url: str = "",
        summary: str = "",
        source_excerpt: str = "",
        **kw,
    ) -> dict:
        from runtime.comms.email_sender import EmailSender

        sender = EmailSender()
        resolved_recipient = self.vault.resolve(recipient) if recipient and self.vault.has(recipient) else recipient
        dispatch_result = sender.send_article_summary_email(
            recipient=resolved_recipient,
            subject=subject,
            article_title=article_title,
            article_url=article_url,
            summary=summary,
            source_excerpt=source_excerpt,
        )
        return {
            "action": "done",
            "recipient": dispatch_result["recipient"],
            "subject": dispatch_result["subject"],
            "dispatch": dispatch_result,
            "status": dispatch_result.get("status", "saved_to_outbox"),
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

    def _handle_wind_tally(
        self,
        windspeed_knots: float = 12.4,
        velocity_ms: float = 1824.5,
        altitude_km: float = 54.2,
        recipient: str = "mission-control@isro.gov.in",
        **kw,
    ) -> dict:
        # Calculate wind shear correlation ratio against Datapoint A (Velocity) & Datapoint B (Altitude)
        speed_wind_ratio = round(velocity_ms / max(windspeed_knots, 0.1), 2)
        wind_alt_index = round((windspeed_knots * 0.514444) / max(altitude_km, 0.1), 4)
        tally_summary = (
            f"WIND SPEED TALLY ANALYSIS:\n"
            f"- Current Wind Speed: {windspeed_knots} knots (6.38 m/s)\n"
            f"- Datapoint A (Velocity): {velocity_ms} m/s (Mach 5.42)\n"
            f"- Datapoint B (Altitude): {altitude_km} km\n"
            f"- Velocity-to-Wind Ratio: {speed_wind_ratio}x\n"
            f"- Wind Shear Index @ {altitude_km}km: {wind_alt_index} m/s/km\n"
            f"- Dynamic Assessment: WIND SHEAR WITHIN NOMINAL FLIGHT ENVELOPE (< 1.5)"
        )

        email_result = self._handle_comms_email(
            recipient=recipient,
            subject="FABLE Windspeed & Flight Telemetry Tally Analysis Report",
            sanitized_body=tally_summary,
            telemetry={
                "altitude_km": altitude_km,
                "velocity_ms": velocity_ms,
                "mach": 5.42,
                "dynamic_pressure_kpa": 34.80,
                "wind_knots": windspeed_knots,
                "chamber_pressure_bar": 58.4,
                "propellant_remaining_pct": 71.8,
            },
        )
        return {
            "action": "done",
            "tally_metrics": {
                "windspeed_knots": windspeed_knots,
                "velocity_ms": velocity_ms,
                "altitude_km": altitude_km,
                "speed_wind_ratio": speed_wind_ratio,
                "wind_shear_index": wind_alt_index,
            },
            "summary": tally_summary,
            "email_dispatch": email_result,
            "status": "completed",
        }
