from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.army.agents import (
    CommsOfficerAgent,
    FlightOpsAgent,
    PrivacyShieldAgent,
    SecurityAuditorAgent,
    TelemetryAnalystAgent,
)
from mcp.gateway import McpGateway
from runtime.privacy import PrivacyFirewall
from runtime.state import ActionRequest, BrowserAction, RawObservation, SanitizedState

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class FableCommander:
    """Supreme Orchestrator: Coordinates the FABLE Legion of Agents and MCP Tool Servers."""

    firewall: PrivacyFirewall
    gateway: McpGateway
    shield_agent: PrivacyShieldAgent = field(init=False)
    analyst_agent: TelemetryAnalystAgent = field(init=False)
    flight_agent: FlightOpsAgent = field(init=False)
    comms_agent: CommsOfficerAgent = field(init=False)
    auditor_agent: SecurityAuditorAgent = field(init=False)

    def __post_init__(self) -> None:
        self.shield_agent = PrivacyShieldAgent(firewall=self.firewall)
        self.analyst_agent = TelemetryAnalystAgent()
        self.flight_agent = FlightOpsAgent(gateway=self.gateway)
        self.comms_agent = CommsOfficerAgent(gateway=self.gateway)
        self.auditor_agent = SecurityAuditorAgent()

    def execute_directive(self, observation: RawObservation, directive: str) -> dict[str, Any]:
        """Runs multi-agent coordinated execution for a human mission directive."""
        print(f"\n[FABLE COMMANDER] Incoming Human Directive: \"{directive}\"")
        print("[FABLE COMMANDER] Deploying Agent Army across MCP tool matrix...")

        # 1. SHIELD AGENT: Privacy Screening & Redaction
        sanitized_state, shield_stats = self.shield_agent.redact_and_sanitize(observation)
        print(f"   * [SHIELD] [{self.shield_agent.name}] Redacted CAD & {shield_stats['tokens_redacted']} classified tokens.")

        # 2. ANALYST AGENT: Flight Dynamics & Telemetry Analysis
        analysis_report = self.analyst_agent.analyze_telemetry(sanitized_state)
        telemetry_metrics = analysis_report["metrics"]
        print(f"   * [ANALYST] [{self.analyst_agent.name}] Flight Nominal: Alt {telemetry_metrics['altitude_km']}km, Vel {telemetry_metrics['velocity_ms']}m/s (Mach {telemetry_metrics['mach']}).")

        # 3. FLIGHT OPS AGENT: Physical Actuation
        flight_action = self.flight_agent.plan_flight_action(directive, sanitized_state)
        if flight_action.action != BrowserAction.DONE:
            print(f"   * [PILOT] [{self.flight_agent.name}] Planned Action: {flight_action.action.value} -> {flight_action.element_id}")

        # 4. COMMS OFFICER AGENT: Email Dispatch (if requested in directive)
        comms_result = None
        email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", directive)
        if "email" in directive.lower() or "mail" in directive.lower() or "report" in directive.lower() or email_match:
            recipient = email_match.group(0) if email_match else "mission-control@isro.gov.in"
            comms_result = self.comms_agent.dispatch_report(recipient, telemetry_metrics)
            dispatch_info = comms_result.get("dispatch_info", {})
            print(f"   * [COMMS] [{self.comms_agent.name}] Email Dispatch -> {recipient}")
            if dispatch_info.get("smtp_sent"):
                print(f"      [SMTP LIVE] Delivered successfully via smtp.gmail.com")
            else:
                print(f"      [OUTBOX FILE] Saved to {dispatch_info.get('outbox_html')}")

        # 5. SECURITY AUDITOR AGENT: Compliance & Zero-Leak Certification
        audit_result = self.auditor_agent.audit_mission_cycle(sanitized_state, flight_action)
        print(f"   * [AUDITOR] [{self.auditor_agent.name}] Compliance: {audit_result['compliance']} ({audit_result['policy_decision']})")


        # Save structured telemetry JSON
        telemetry_file = ROOT / "launch_telemetry_sanitized.json"
        summary = {
            "mission": "FABLE / ISRO LVM3-M4 MISSION ORCHESTRATION",
            "commander_directive": directive,
            "army_of_agents": {
                "privacy_shield": shield_stats,
                "flight_dynamics": analysis_report,
                "flight_actuation": {
                    "action": flight_action.action.value,
                    "target_element": flight_action.element_id,
                    "reasoning": flight_action.reasoning,
                },
                "comms_dispatch": comms_result,
                "security_audit": audit_result,
            },
            "sanitized_telemetry": telemetry_metrics,
        }
        telemetry_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

        # Build MCP browser command if actuation occurred
        browser_command = None
        if flight_action.action != BrowserAction.DONE:
            from runtime.state import ApprovedAction, PolicyDecision
            approved = ApprovedAction(flight_action, PolicyDecision.ALLOW)
            browser_command = self.gateway.browser_command(approved)
        elif comms_result:
            from runtime.state import ApprovedAction, PolicyDecision
            email_action = ActionRequest(
                BrowserAction.CLICK,
                element_id="btn-send-telemetry-report",
                reasoning=f"Dispatched flight test report to {comms_result['recipient']}",
            )
            browser_command = self.gateway.browser_command(ApprovedAction(email_action, PolicyDecision.ALLOW))

        return {
            "status": audit_result["policy_decision"],
            "state": sanitized_state,
            "command": browser_command,
            "army_summary": summary,
            "reasoning": flight_action.reasoning if flight_action.action != BrowserAction.DONE else "FABLE Multi-Agent directive executed.",
        }
