#!/usr/bin/env python3
"""
FABLE — Privacy-First Autonomous Multi-Agent & MCP Army
Equipped with Defense-Grade Privacy Firewall & Redaction Shield
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.army import FableCommander
from mcp.gateway import McpGateway
from runtime.comms.email_sender import load_project_env
from runtime.privacy import FaceDetector, ImageRedactor, PrivacyDetector, PrivacyFirewall, VisualClassifier
from runtime.state import DomElement, RawDom, RawObservation
from runtime.tokenization import TokenVault


def create_fable_system() -> tuple[FableCommander, McpGateway]:
    load_project_env()
    vault = TokenVault()
    gateway = McpGateway(vault)
    face_detector = FaceDetector() if os.getenv("FACE_DETECTION", "1") == "1" else None
    visual_classifier = VisualClassifier()

    firewall = PrivacyFirewall(
        detector=PrivacyDetector(vault),
        redactor=ImageRedactor(),
        face_detector=face_detector,
        visual_classifier=visual_classifier,
        mode=os.getenv("PRIVACY_MODE", "STRICT"),
    )
    commander = FableCommander(firewall=firewall, gateway=gateway)
    return commander, gateway


def print_fable_banner(gateway: McpGateway):
    print("=" * 78)
    print("  ______ ___  ______ _      _____ ")
    print("  |  ___/ _ \\ | ___ \\ |    |  ___|")
    print("  | |_ / /_\\ \\| |_/ / |    | |__  ")
    print("  |  _||  _  || ___ \\ |    |  __| ")
    print("  | |  | | | || |_/ / |____| |___ ")
    print("  \\_|  \\_| |_/\\____/\\_____/\\____/ ")
    print("   PRIVACY-FIRST MULTI-AGENT & MCP ARMY FOR DEFENSE & AEROSPACE")
    print("=" * 78)
    print("[FABLE AGENT ARMY STANDING BY]")
    print("   1. SHIELD-1   : Privacy & Redaction Officer (CAD Blur / Key Tokenizer)")
    print("   2. ANALYST-2  : Flight Dynamics & Max-Q Telemetry Officer (20Hz Stream)")
    print("   3. PILOT-3    : Simulation & Flight Actuation Officer (MCP Pilot)")
    print("   4. COMMS-4    : Mission Intelligence & Secure Email Officer (SMTP/Outbox)")
    print("   5. AUDITOR-5  : Security Sentinel & Zero-Leak Policy Officer")
    print("\n[ACTIVE MCP TOOL REGISTRY]")
    for tool in gateway.registry.list_tools():
        print(f"   * [{tool['name']}] -> {tool['description']}")
    print("=" * 78)


def run_fable_directive(commander: FableCommander, directive: str) -> dict:
    raw_obs = RawObservation(
        session_id=f"fable-{int(time.time())}",
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

    result = commander.execute_directive(raw_obs, directive)
    print("\n[FABLE MISSION SUMMARY]")
    print(f"   * Status           : {result['status']}")
    print(f"   * Coordinated Plan : {result['reasoning']}")
    print(f"   * Artifact Saved   : launch_telemetry_sanitized.json")
    print("=" * 78)
    return result


def main():
    commander, gateway = create_fable_system()
    print_fable_banner(gateway)

    if len(sys.argv) > 1:
        directive = " ".join(sys.argv[1:])
        run_fable_directive(commander, directive)
    else:
        print("\nEnter a mission directive for the FABLE Agent Army (or 'exit' to quit):")
        while True:
            try:
                cmd = input("\nFABLE >> ").strip()
                if not cmd or cmd.lower() in ("exit", "quit", "q"):
                    print("[FABLE] Agent Legion standing down. Mission control offline.")
                    break
                run_fable_directive(commander, cmd)
            except (KeyboardInterrupt, EOFError):
                print("\n[FABLE] Agent Legion standing down.")
                break


if __name__ == "__main__":
    main()
