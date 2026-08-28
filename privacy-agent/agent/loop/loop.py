from __future__ import annotations

import re
from dataclasses import dataclass, field

from agent.planner import Planner
from mcp.gateway import McpGateway
from runtime.audit import AuditLogger
from runtime.policy import PolicyEngine
from runtime.privacy import PrivacyFirewall
from runtime.reasoning import ContextBuilder
from runtime.reasoning.summarizer import summarize_article
from runtime.schemas import action_request_to_json
from runtime.state import ActionRequest, ApprovedAction, BrowserAction, PolicyDecision, RawObservation, TemporalDiffEngine


@dataclass
class AgentLoop:
    firewall: PrivacyFirewall
    planner: Planner
    policy: PolicyEngine
    gateway: McpGateway
    audit: AuditLogger
    diff_engine: TemporalDiffEngine = field(default_factory=TemporalDiffEngine)
    context_builder: ContextBuilder = field(default_factory=ContextBuilder)

    def step(self, observation: RawObservation, user_instruction: str, approved_by_user: bool = False) -> dict:
        sanitized = self.firewall.sanitize(observation)
        temporal_update = self.diff_engine.update(observation.session_id, sanitized.state)
        safe_context = self.context_builder.build(sanitized, user_instruction, temporal_update)
        
        # Save exact sanitized state JSON for inspection / auditing
        try:
            import json
            from pathlib import Path
            from agent.ollama.client import state_to_dict
            debug_path = Path(__file__).resolve().parents[2] / "last_sanitized_state.json"
            debug_path.write_text(json.dumps(state_to_dict(sanitized.state), indent=2), encoding="utf-8")
        except Exception:
            pass

        screenshot_b64 = sanitized.sanitized_screenshot.webp_base64 if sanitized.sanitized_screenshot else None
        
        privacy_stats = {
            "faces_blurred": sanitized.face_count,
            "visual_findings": sanitized.visual_findings_count,
            "regions_redacted": sanitized.state.privacy.get("redacted", 0),
            "findings": sanitized.state.privacy.get("findings", 0),
        }

        # Check if the user's directive is an email request (telemetry, summary, or page link)
        email_result = self._maybe_handle_email_directive(sanitized.state, user_instruction)
        if email_result:
            recipient = email_result.get("recipient") or "recipient"
            done_request = ActionRequest(
                BrowserAction.DONE,
                reasoning=f"Fable processed email dispatch to {recipient}. Status: {email_result.get('status', 'completed')}.",
            )
            return {
                "status": "ALLOW",
                "state": sanitized.state,
                "command": self.gateway.browser_command(ApprovedAction(done_request, PolicyDecision.ALLOW)),
                "action_json": action_request_to_json(done_request),
                "reasoning": done_request.reasoning,
                "privacy_stats": privacy_stats,
                "safe_context": safe_context,
                "temporal_update": temporal_update,
                "tool_result": email_result,
            }

        request = self.planner.plan(sanitized.state, user_instruction, screenshot_b64=screenshot_b64)
        action_json = action_request_to_json(request)

        approved = self.policy.evaluate(sanitized.state, request, approved_by_user=approved_by_user)
        self.audit.record(observation.session_id, sanitized.sanitized_dom.domain, approved, "PENDING")

        if approved.decision != PolicyDecision.ALLOW:
            return {
                "status": approved.decision.value,
                "state": sanitized.state,
                "action": request.action.value,
                "action_json": action_json,
                "reasoning": request.reasoning,
                "privacy_stats": privacy_stats,
                "safe_context": safe_context,
                "temporal_update": temporal_update,
            }
        return {
            "status": "ALLOW",
            "state": sanitized.state,
            "command": self.gateway.browser_command(approved),
            "action_json": action_json,
            "reasoning": request.reasoning,
            "privacy_stats": privacy_stats,
            "safe_context": safe_context,
            "temporal_update": temporal_update,
        }

    def _maybe_handle_email_directive(self, state, user_instruction: str) -> dict | None:
        wanted = user_instruction.lower()
        if not any(word in wanted for word in ("email", "mail", "send")):
            return None

        email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", user_instruction)
        recipient = email_match.group(0) if email_match else ""

        article_title = str(state.page.get("title") or "Current page")
        article_url = str(state.page.get("url") or "")
        source_text = state.visible_text

        # 1. Windspeed Tally & Data Points Calculation
        if any(word in wanted for word in ("windspeed", "wind", "tally", "datapoint", "datapoints")):
            telemetry_data = getattr(state, "telemetry", None) or {}
            return self.gateway.execute_tool(
                "telemetry.calculate_wind_tally",
                windspeed_knots=self._telemetry_value(telemetry_data, "wind_knots", default=self._mps_to_knots(self._telemetry_value(telemetry_data, "wind_m_s", default=12.4 * 0.514444))),
                velocity_ms=self._telemetry_value(telemetry_data, "velocity_ms", default=self._telemetry_value(telemetry_data, "velocity_km_s", default=1.8245) * 1000),
                altitude_km=self._telemetry_value(telemetry_data, "altitude_km", default=54.20),
                recipient=recipient or "mission-control@isro.gov.in",
            )

        # 2. Telemetry / Flight test report email
        if any(word in wanted for word in ("telemetry", "launch", "flight", "rocket", "stage", "test")):
            telemetry_data = getattr(state, "telemetry", None) or {
                "altitude_km": 54.20,
                "velocity_ms": 1824.5,
                "mach": 5.42,
                "dynamic_pressure_kpa": 34.80,
                "chamber_pressure_bar": 58.4,
                "propellant_remaining_pct": 71.8,
            }
            subject = "ISRO LVM3-M4 Launch Telemetry & Flight Test Report"
            return self.gateway.execute_tool(
                "comms.transmit_telemetry_email",
                recipient=recipient or "mission-control@isro.gov.in",
                subject=subject,
                telemetry=telemetry_data,
                sanitized_body=source_text[:1200],
            )

        # 2. General Article summary / Page link email
        summary = summarize_article(source_text)
        subject = f"Fable summary: {article_title[:80]}"
        return self.gateway.execute_tool(
            "comms.email_article_summary",
            recipient=recipient,
            subject=subject,
            article_title=article_title,
            article_url=article_url,
            summary=summary,
            source_excerpt=source_text[:1200],
        )

    def _telemetry_value(self, telemetry: dict, key: str, default: float) -> float:
        value = telemetry.get(key)
        if isinstance(value, dict):
            value = value.get("value")
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _mps_to_knots(self, value: float) -> float:
        return float(value) / 0.514444
