from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from runtime.state import ApprovedAction, PolicyDecision


@dataclass
class AuditLogger:
    path: Path

    def record(self, session_id: str, domain: str, approved: ApprovedAction, result: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "domain": domain,
            "action": approved.request.action.value,
            "target": approved.request.element_id,
            "policy_decision": approved.decision.value,
            "approval_status": "approved" if approved.decision == PolicyDecision.ALLOW else "not_approved",
            "result": result,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")

