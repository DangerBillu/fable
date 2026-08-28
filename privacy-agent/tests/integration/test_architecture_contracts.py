import base64
import io
import sys
import unittest
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from agent.loop import AgentLoop
from agent.planner import Planner
from mcp.gateway import McpGateway
from runtime.audit import AuditLogger
from runtime.perception import TelemetryExtractor
from runtime.policy import PolicyEngine
from runtime.privacy import ImageRedactor, PrivacyDetector, PrivacyFirewall
from runtime.schemas import validate_action_json, validate_observation_json
from runtime.state import DomElement, RawDom, RawObservation, RawScreenshot
from runtime.tokenization import TokenVault


class ArchitectureContractTests(unittest.TestCase):
    def _make_loop(self):
        vault = TokenVault()
        return AgentLoop(
            firewall=PrivacyFirewall(
                detector=PrivacyDetector(vault),
                redactor=ImageRedactor(),
                telemetry_extractor=TelemetryExtractor(confidence=0.99),
            ),
            planner=Planner(),
            policy=PolicyEngine(mode="STRICT"),
            gateway=McpGateway(vault),
            audit=AuditLogger(ROOT / "tmp-contract-audit.log"),
        )

    def test_safe_context_contains_telemetry_and_no_raw_secret(self):
        loop = self._make_loop()
        result = loop.step(
            RawObservation(
                session_id="rocket-1",
                raw_dom=RawDom(
                    title="Rocket Simulation",
                    url="https://sim.example.local/launch",
                    visible_text=(
                        "Project Engine Diagram. Operator john@example.com. "
                        "Status Running Altitude 124.82 km Velocity 7.82 km/s "
                        "Wind 14.2 m/s Fuel 73.2%"
                    ),
                    elements=(DomElement(id="pause", tag="button", text="Pause", bbox=(8, 8, 80, 32)),),
                ),
            ),
            "Monitor the launch and collect safe telemetry.",
        )

        context_text = str(result["safe_context"])
        self.assertNotIn("john@example.com", context_text)
        self.assertIn("EMAIL_", context_text)
        self.assertEqual(result["safe_context"]["trust_boundary"], "raw_pixels_and_raw_ocr_excluded")
        self.assertEqual(result["state"].telemetry["altitude_km"]["value"], 124.82)
        self.assertEqual(result["state"].telemetry["velocity_km_s"]["value"], 7.82)
        self.assertEqual(result["state"].telemetry["wind_m_s"]["value"], 14.2)
        self.assertEqual(result["state"].telemetry["fuel_percent"]["value"], 73.2)
        validate_observation_json(result["safe_context"]["observation"])
        validate_action_json(result["action_json"])

    def test_temporal_diff_reports_incremental_changes(self):
        loop = self._make_loop()
        first = RawObservation(
            session_id="rocket-diff",
            raw_dom=RawDom(
                title="Rocket Simulation",
                url="https://sim.example.local/launch",
                visible_text="Status Running Altitude 124.82 km Velocity 7.82 km/s Fuel 73.2%",
                elements=(),
            ),
        )
        second = RawObservation(
            session_id="rocket-diff",
            raw_dom=RawDom(
                title="Rocket Simulation",
                url="https://sim.example.local/launch",
                visible_text="Status Running Altitude 125.31 km Velocity 7.86 km/s Fuel 72.9%",
                elements=(),
            ),
        )

        loop.step(first, "Collect safe telemetry.")
        result = loop.step(second, "Collect safe telemetry.")

        self.assertEqual(result["temporal_update"]["event"], "telemetry_update")
        self.assertEqual(result["temporal_update"]["changed"]["altitude_km"], {"previous": 124.82, "current": 125.31})
        self.assertEqual(result["temporal_update"]["changed"]["velocity_km_s"], {"previous": 7.82, "current": 7.86})

    def test_screenshot_region_is_redacted_before_context(self):
        image = Image.new("RGB", (180, 80), color=(240, 240, 240))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        data_url = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"

        loop = self._make_loop()
        result = loop.step(
            RawObservation(
                session_id="rocket-image",
                raw_dom=RawDom(
                    title="Rocket Simulation",
                    url="https://sim.example.local/launch",
                    visible_text="API token sk-test-secret-1234567890 Altitude 10 km",
                    elements=(DomElement(id="secret", tag="div", text="sk-test-secret-1234567890", bbox=(10, 10, 90, 30)),),
                ),
                raw_screenshot=RawScreenshot(data_url),
            ),
            "Collect safe telemetry.",
        )

        context_text = str(result["safe_context"])
        self.assertNotIn("sk-test-secret-1234567890", context_text)
        self.assertGreaterEqual(result["privacy_stats"]["regions_redacted"], 1)


if __name__ == "__main__":
    unittest.main()
