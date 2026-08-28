import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.loop import AgentLoop
from agent.planner import Planner
from mcp.gateway import McpGateway
from runtime.audit import AuditLogger
from runtime.policy import PolicyEngine
from runtime.privacy import FaceDetector, ImageRedactor, PrivacyDetector, PrivacyFirewall, VisualClassifier
from runtime.state import DomElement, FaceRegion, RawDom, RawObservation, RawScreenshot
from runtime.tokenization import TokenVault


class DemoLoopTests(unittest.TestCase):
    def _make_loop(self):
        vault = TokenVault()
        return AgentLoop(
            firewall=PrivacyFirewall(
                detector=PrivacyDetector(vault),
                redactor=ImageRedactor(),
                face_detector=FaceDetector(),
                visual_classifier=VisualClassifier(),
            ),
            planner=Planner(),
            policy=PolicyEngine(mode="STRICT"),
            gateway=McpGateway(vault),
            audit=AuditLogger(ROOT / "tmp-test-audit.log"),
        )

    def test_open_settings_demo_path(self):
        loop = self._make_loop()
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

    def test_privacy_stats_in_response(self):
        """The step response should include privacy_stats."""
        loop = self._make_loop()
        result = loop.step(
            RawObservation(
                session_id="demo-stats",
                raw_dom=RawDom(
                    title="Test Page",
                    url="https://example.com",
                    visible_text="Contact: test@example.com",
                    elements=(DomElement(id="btn_1", tag="button", text="Settings", bbox=(10, 10, 80, 30)),),
                ),
            ),
            "Open the settings page.",
        )
        self.assertIn("privacy_stats", result)
        stats = result["privacy_stats"]
        self.assertIn("faces_blurred", stats)
        self.assertIn("visual_findings", stats)
        self.assertIn("regions_redacted", stats)
        self.assertIn("findings", stats)

    def test_face_regions_from_browser(self):
        """Browser-reported face regions should be processed."""
        from PIL import Image
        import base64, io
        # Create a small synthetic screenshot as data URL
        img = Image.new("RGB", (200, 200), color=(200, 200, 200))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        screenshot_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        screenshot_data_url = f"data:image/png;base64,{screenshot_b64}"

        loop = self._make_loop()
        result = loop.step(
            RawObservation(
                session_id="demo-faces",
                raw_dom=RawDom(
                    title="Test Page",
                    url="https://example.com",
                    visible_text="Hello world",
                    elements=(DomElement(id="btn_1", tag="button", text="Settings", bbox=(10, 10, 80, 30)),),
                ),
                raw_screenshot=RawScreenshot(screenshot_data_url),
                face_regions=(
                    FaceRegion(x=50, y=50, width=100, height=100, confidence=0.9, source="browser"),
                ),
            ),
            "Open the settings page.",
        )
        # Face count should be included in privacy stats
        self.assertGreaterEqual(result["privacy_stats"]["faces_blurred"], 1)


    def test_isro_patterns_detected(self):
        """ISRO-specific patterns (Aadhaar, PAN) should be detected and tokenized."""
        loop = self._make_loop()
        result = loop.step(
            RawObservation(
                session_id="demo-isro",
                raw_dom=RawDom(
                    title="Employee Portal",
                    url="https://internal.isro.gov.in",
                    visible_text="Employee: Ravi Kumar | Aadhaar: 1234 5678 9012 | PAN: ABCDE1234F",
                    elements=(DomElement(id="settings_1", tag="button", text="Settings", bbox=(20, 20, 90, 40)),),
                ),
            ),
            "Open the settings page.",
        )
        state_str = str(result["state"])
        # Raw Aadhaar and PAN should be tokenized, not present in sanitized state
        self.assertNotIn("1234 5678 9012", state_str)
        self.assertNotIn("ABCDE1234F", state_str)

    def test_wind_tally_uses_screen_telemetry(self):
        loop = self._make_loop()
        with patch("runtime.comms.email_sender.EmailSender.send_telemetry_email") as send:
            send.return_value = {
                "recipient": "flight.director@example.com",
                "subject": "FABLE Windspeed & Flight Telemetry Tally Analysis Report",
                "smtp_configured": False,
                "smtp_sent": False,
                "status": "saved_to_outbox",
            }
            result = loop.step(
                RawObservation(
                    session_id="demo-wind",
                    raw_dom=RawDom(
                        title="Launch Telemetry",
                        url="https://example.com",
                        visible_text=(
                            "Cross-Wind Shear 14.8 KNOTS. "
                            "Datapoint A Velocity 1,900.5 meters/sec. "
                            "Datapoint B Altitude 62.7 km."
                        ),
                        elements=(),
                    ),
                ),
                "Get the current windspeed and tally it with datapoints A and B on the screen and send the response to flight.director@example.com email.",
                approved_by_user=True,
            )

        self.assertEqual(result["status"], "ALLOW")
        self.assertEqual(result["command"]["action"], "done")
        metrics = result["tool_result"]["tally_metrics"]
        self.assertEqual(metrics["windspeed_knots"], 14.8)
        self.assertEqual(metrics["velocity_ms"], 1900.5)
        self.assertEqual(metrics["altitude_km"], 62.7)


if __name__ == "__main__":
    unittest.main()
