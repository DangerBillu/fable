import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from mcp.gateway import McpGateway
from mcp.registry import McpRegistry, McpTool
from runtime.state import ActionRequest, ApprovedAction, BrowserAction, PolicyDecision
from runtime.tokenization import TokenVault


class McpTeamTests(unittest.TestCase):
    def setUp(self):
        self.vault = TokenVault()
        self.gateway = McpGateway(self.vault)

    def test_mcp_registry_initialization(self):
        """Verify default Fable MCP tools are registered."""
        tools = self.gateway.registry.list_tools()
        tool_names = [t["name"] for t in tools]
        self.assertIn("flight.trigger_stage_separation", tool_names)
        self.assertIn("flight.jettison_fairing", tool_names)
        self.assertIn("flight.recalibrate_gimbal", tool_names)
        self.assertIn("comms.transmit_telemetry_email", tool_names)
        self.assertIn("comms.email_article_summary", tool_names)
        self.assertIn("telemetry.analyze_flight_safety", tool_names)

    def test_flight_actuator_mcp_execution(self):
        """Test direct execution of flight stage separation tool."""
        res = self.gateway.execute_tool("flight.trigger_stage_separation")
        self.assertEqual(res["action"], "click")
        self.assertEqual(res["element_id"], "btn-stage-sep")
        self.assertEqual(res["status"], "executed")

    def test_telemetry_analyst_mcp_execution(self):
        """Test telemetry analysis tool safety thresholds."""
        res = self.gateway.execute_tool(
            "telemetry.analyze_flight_safety",
            altitude_km=55.0,
            velocity_ms=1850.0,
            dynamic_pressure_kpa=32.0,
        )
        self.assertTrue(res["max_q_cleared"])
        self.assertTrue(res["staging_ready"])
        self.assertEqual(res["recommended_action"], "flight.trigger_stage_separation")

    def test_comms_dispatch_mcp_execution(self):
        """Test comms email dispatch tool."""
        with patch("runtime.comms.email_sender.EmailSender.send_telemetry_email") as send:
            send.return_value = {
                "recipient": "flight.director@isro.gov.in",
                "subject": "LVM3 Telemetry Report",
                "smtp_configured": True,
                "smtp_sent": True,
                "smtp_error_code": None,
                "smtp_error": None,
                "outbox_html": "outbox/latest_flight_report.html",
                "outbox_eml": "outbox/latest_flight_report.eml",
                "status": "delivered_to_smtp",
            }
            res = self.gateway.execute_tool(
                "comms.transmit_telemetry_email",
                recipient="flight.director@isro.gov.in",
                subject="LVM3 Telemetry Report",
            )
        self.assertEqual(res["action"], "click")
        self.assertEqual(res["element_id"], "btn-send-telemetry-report")
        self.assertEqual(res["recipient"], "flight.director@isro.gov.in")
        self.assertEqual(res["status"], "delivered_to_smtp")


if __name__ == "__main__":
    unittest.main()
