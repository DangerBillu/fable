from __future__ import annotations

from dataclasses import dataclass

from agent.planner import Planner
from mcp.gateway import McpGateway
from runtime.audit import AuditLogger
from runtime.policy import PolicyEngine
from runtime.privacy import PrivacyFirewall
from runtime.state import PolicyDecision, RawObservation


@dataclass
class AgentLoop:
    firewall: PrivacyFirewall
    planner: Planner
    policy: PolicyEngine
    gateway: McpGateway
    audit: AuditLogger

    def step(self, observation: RawObservation, user_instruction: str, approved_by_user: bool = False) -> dict:
        sanitized = self.firewall.sanitize(observation)
        request = self.planner.plan(sanitized.state, user_instruction)
        approved = self.policy.evaluate(sanitized.state, request, approved_by_user=approved_by_user)
        self.audit.record(observation.session_id, sanitized.sanitized_dom.domain, approved, "PENDING")
        if approved.decision != PolicyDecision.ALLOW:
            return {
                "status": approved.decision.value,
                "state": sanitized.state,
                "action": request.action.value,
                "reasoning": request.reasoning,
            }
        return {
            "status": "ALLOW",
            "state": sanitized.state,
            "command": self.gateway.browser_command(approved),
            "reasoning": request.reasoning,
        }

