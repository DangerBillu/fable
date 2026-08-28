import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.loop import AgentLoop
from agent.planner import Planner
from mcp.gateway import McpGateway
from runtime.audit import AuditLogger
from runtime.policy import PolicyEngine
from runtime.privacy import ImageRedactor, PrivacyDetector, PrivacyFirewall
from runtime.state import DomElement, RawDom, RawObservation
from runtime.tokenization import TokenVault


class DemoLoopTests(unittest.TestCase):
    def test_open_settings_demo_path(self):
        vault = TokenVault()
        loop = AgentLoop(
            firewall=PrivacyFirewall(PrivacyDetector(vault), ImageRedactor()),
            planner=Planner(),
            policy=PolicyEngine(mode="STRICT"),
            gateway=McpGateway(vault),
            audit=AuditLogger(ROOT / "tmp-test-audit.log"),
        )
        result = loop.step(
            RawObservation(
                session_id="demo",
                raw_dom=RawDom(
                    title="Company Dashboard",
                    url="https://example.com",
                    visible_text="Employee John Doe Email john@example.com Phone +91 9876543210 Project Alpha Revenue ₹52,431",
                    elements=(DomElement(id="settings_1", tag="button", text="Settings", bbox=(20, 20, 90, 40)),),
                ),
            ),
            "Open the settings page.",
        )
        self.assertEqual(result["status"], "ALLOW")
        self.assertEqual(result["command"]["action"], "click")
        self.assertEqual(result["command"]["element_id"], "settings_1")
        self.assertNotIn("john@example.com", str(result["state"]))


if __name__ == "__main__":
    unittest.main()

