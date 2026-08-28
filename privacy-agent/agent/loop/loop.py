from __future__ import annotations

from dataclasses import dataclass, field

from agent.planner import Planner
from mcp.gateway import McpGateway
from runtime.audit import AuditLogger
from runtime.policy import PolicyEngine
from runtime.privacy import PrivacyFirewall
from runtime.reasoning import ContextBuilder
from runtime.schemas import action_request_to_json
from runtime.state import PolicyDecision, RawObservation, TemporalDiffEngine


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
        request = self.planner.plan(sanitized.state, user_instruction, screenshot_b64=screenshot_b64)
        action_json = action_request_to_json(request)

        approved = self.policy.evaluate(sanitized.state, request, approved_by_user=approved_by_user)
        self.audit.record(observation.session_id, sanitized.sanitized_dom.domain, approved, "PENDING")
        
        privacy_stats = {
            "faces_blurred": sanitized.face_count,
            "visual_findings": sanitized.visual_findings_count,
            "regions_redacted": sanitized.state.privacy.get("redacted", 0),
            "findings": sanitized.state.privacy.get("findings", 0),
        }
        
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
