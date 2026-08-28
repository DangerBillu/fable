from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.loop import AgentLoop
from agent.planner import Planner
from mcp.gateway import McpGateway
from runtime.audit import AuditLogger
from runtime.policy import PolicyEngine
from runtime.privacy import ImageRedactor, PrivacyDetector, PrivacyFirewall
from runtime.state import DomElement, RawDom, RawObservation, RawScreenshot
from runtime.tokenization import TokenVault


vault = TokenVault()
loop = AgentLoop(
    firewall=PrivacyFirewall(PrivacyDetector(vault), ImageRedactor(), mode=os.getenv("PRIVACY_MODE", "STRICT")),
    planner=Planner(),
    policy=PolicyEngine(mode=os.getenv("PRIVACY_MODE", "STRICT")),
    gateway=McpGateway(vault),
    audit=AuditLogger(ROOT / "audit.log"),
)


class Handler(BaseHTTPRequestHandler):
    server_version = "PrivacyAgentStdlib/0.1"

    def do_OPTIONS(self) -> None:
        self._send_json(200, {})

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"status": "ok", "privacy": "local-only"})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/agent/step":
            self._send_json(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("content-length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = loop.step(parse_observation(payload), payload["user_instruction"], bool(payload.get("approved_by_user")))
            self._send_json(200, result)
        except Exception as exc:
            self._send_json(400, {"error": str(exc)})

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(to_jsonable(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(body)


def parse_observation(payload: dict) -> RawObservation:
    return RawObservation(
        session_id=payload.get("session_id") or str(uuid4()),
        raw_dom=RawDom(
            title=payload.get("title", ""),
            url=payload.get("url", ""),
            visible_text=payload.get("visible_text", ""),
            elements=tuple(DomElement(**element) for element in payload.get("elements", [])),
        ),
        raw_screenshot=RawScreenshot(payload["screenshot_data_url"]) if payload.get("screenshot_data_url") else None,
    )


def to_jsonable(value):
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: to_jsonable(getattr(value, key)) for key in value.__dataclass_fields__ if not key.startswith("_")}
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value


def main() -> None:
    host = "127.0.0.1"
    port = int(os.getenv("PORT", "8000"))
    print(f"Privacy Agent runtime listening on http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()

