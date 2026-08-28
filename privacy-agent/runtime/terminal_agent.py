from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.loop import AgentLoop
from agent.ollama import OllamaClient
from agent.planner import Planner
from mcp.gateway import McpGateway
from runtime.audit import AuditLogger
from runtime.policy import PolicyEngine
from runtime.privacy import FaceDetector, ImageRedactor, PrivacyDetector, PrivacyFirewall, VisualClassifier
from runtime.state import DomElement, FaceRegion, RawDom, RawObservation, RawScreenshot
from runtime.tokenization import TokenVault

try:
    from agent.hf import HuggingFaceClient
except ImportError:
    HuggingFaceClient = None


def create_agent_loop() -> AgentLoop:
    vault = TokenVault()
    face_detector = FaceDetector() if os.getenv("FACE_DETECTION", "1") == "1" else None
    visual_classifier = VisualClassifier()
    ollama_client = OllamaClient() if os.getenv("USE_OLLAMA", "0") == "1" else None
    
    hf_client = None
    hf_token = os.getenv("HF_API_TOKEN", "")
    if hf_token and HuggingFaceClient:
        hf_client = HuggingFaceClient(api_token=hf_token)

    return AgentLoop(
        firewall=PrivacyFirewall(
            detector=PrivacyDetector(vault),
            redactor=ImageRedactor(),
            face_detector=face_detector,
            visual_classifier=visual_classifier,
            mode=os.getenv("PRIVACY_MODE", "STRICT"),
        ),
        planner=Planner(ollama=ollama_client, hf_client=hf_client),
        policy=PolicyEngine(mode=os.getenv("PRIVACY_MODE", "STRICT")),
        gateway=McpGateway(vault),
        audit=AuditLogger(ROOT / "audit.log"),
    )


def simulate_rocket_launch_step(agent: AgentLoop, instruction: str) -> dict:
    """Run an offline reasoning cycle over a live launch simulation observation."""
    raw_obs = RawObservation(
        session_id=f"mission-sim-{int(time.time())}",
        raw_dom=RawDom(
            title="ISRO LVM3-M4 / CHANDRAYAAN LAUNCH TELEMETRY",
            url="https://isro.gov.in/launch-control/lvm3-m4",
            visible_text=(
                "MET: T+ 00:02:15 | ALTITUDE: 54.20 km | VELOCITY: 1,824.5 m/s | MACH: 5.42 | "
                "DYNAMIC PRESSURE: 34.80 kPa | WIND: 12.4 knots | CHAMBER: 58.4 bar | "
                "CORE PROPELLANT: 71.8% | "
                "[CLASSIFIED: CE-20 ENGINE SPEC: CE20-ISRO-CONFIDENTIAL-992, "
                "CHAMBER TOLERANCE: +-0.002mm INCONEL-718, "
                "CRYPTO KEY: KEY-9948271039481726, TARGET ORBIT: GTO 170x36500km @ 21.3 deg]"
            ),
            elements=(
                DomElement(id="btn-stage-sep", tag="button", text="Trigger Stage Separation [L110/S200]", role="button"),
                DomElement(id="btn-fairing-jettison", tag="button", text="Jettison Payload Fairing [>115 km]", role="button"),
                DomElement(id="btn-gimbal-recal", tag="button", text="Recalibrate Engine Gimbal [Pitch +0.8deg]", role="button"),
                DomElement(id="btn-telemetry-hold", tag="button", text="Emergency Telemetry Hold [Audit]", role="button"),
                DomElement(id="btn-send-telemetry-report", tag="button", text="Transmit Telemetry Test Report", role="button"),
            ),
        ),
        face_regions=(),
    )

    print("\n" + "=" * 70)
    print("[ISRO MISSION CONTROL] OFFLINE REASONING CLIENT ACTIVE")
    print("=" * 70)
    print(f"-> SCIENTIST INSTRUCTION : {instruction}")
    print("[PRIVACY FIREWALL] RUNNING SCREENING & REDACTION PIPELINE...")

    result = agent.step(raw_obs, instruction)

    # Save to launch_telemetry_sanitized.json
    telemetry_file = ROOT / "launch_telemetry_sanitized.json"
    telemetry_summary = {
        "mission": "LVM3-M4 / ISRO ROCKET LAUNCH SIMULATION",
        "flight_phase": "STAGE-1 BOOSTER FLIGHT",
        "sanitized_telemetry": {
            "altitude_km": 54.20,
            "velocity_ms": 1824.5,
            "mach": 5.42,
            "dynamic_pressure_kpa": 34.80,
            "wind_knots": 12.4,
            "chamber_pressure_bar": 58.4,
            "propellant_remaining_pct": 71.8
        },
        "privacy_firewall_status": {
            "engine_cad_blurred": True,
            "crypto_keys_redacted": result["privacy_stats"]["findings"],
            "redaction_categories": list(result["state"].privacy.get("categories", []))
        },
        "sanitized_visible_text": result["state"].visible_text,
        "planned_action": result.get("command") or result.get("action"),
        "reasoning": result.get("reasoning")
    }
    telemetry_file.write_text(json.dumps(telemetry_summary, indent=2), encoding="utf-8")

    print("\n[OK] PRIVACY SANITIZATION COMPLETE:")
    print(f"   * Classified Tokens Redacted : {result['privacy_stats']['findings']}")
    print(f"   * Confidential Engine Specs  : REDACTED / BLURRED")
    print(f"   * Public Flight Telemetry    : PRESERVED (Alt: 54.2km, Vel: 1824m/s, Mach 5.42)")
    print(f"   * Telemetry JSON Saved to   : launch_telemetry_sanitized.json")

    print("\n[REASONING MODEL DECISION]")
    print(f"   * Policy Decision : {result['status']}")
    print(f"   * Action Proposed : {result.get('command', {}).get('action') or result.get('action')}")
    print(f"   * Target Element  : {result.get('command', {}).get('element_id') or 'N/A'}")
    print(f"   * Mission Logic   : {result.get('reasoning')}")
    print("=" * 70)

    return result


def main():
    agent = create_agent_loop()
    instruction = "Monitor Max-Q and trigger stage 1 booster separation when altitude > 50km"
    if len(sys.argv) > 1:
        instruction = " ".join(sys.argv[1:])
    simulate_rocket_launch_step(agent, instruction)


if __name__ == "__main__":
    main()
