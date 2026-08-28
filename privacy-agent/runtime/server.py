from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.loop import AgentLoop
from agent.ollama import OllamaClient
from agent.planner import Planner
from mcp.gateway import McpGateway
from runtime.audit import AuditLogger
from runtime.policy import PolicyEngine
from runtime.privacy import ImageRedactor, PrivacyDetector, PrivacyFirewall
from runtime.state import DomElement, RawDom, RawObservation, RawScreenshot
from runtime.tokenization import TokenVault


class ElementPayload(BaseModel):
    id: str
    tag: str
    role: str | None = None
    aria_label: str | None = None
    text: str | None = None
    input_type: str | None = None
    placeholder: str | None = None
    autocomplete: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    enabled: bool = True
    href: str | None = None
    value: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ObservationPayload(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    user_instruction: str
    title: str
    url: str
    visible_text: str = ""
    elements: list[ElementPayload]
    screenshot_data_url: str | None = None
    approved_by_user: bool = False


vault = TokenVault()
app = FastAPI(title="Privacy Agent Runtime", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost", "chrome-extension://*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

loop = AgentLoop(
    firewall=PrivacyFirewall(PrivacyDetector(vault), ImageRedactor(), mode=os.getenv("PRIVACY_MODE", "STRICT")),
    planner=Planner(OllamaClient() if os.getenv("USE_OLLAMA", "0") == "1" else None),
    policy=PolicyEngine(mode=os.getenv("PRIVACY_MODE", "STRICT")),
    gateway=McpGateway(vault),
    audit=AuditLogger(ROOT / "audit.log"),
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "privacy": "local-only"}


@app.post("/agent/step")
def agent_step(payload: ObservationPayload) -> dict:
    try:
        observation = RawObservation(
            session_id=payload.session_id,
            raw_dom=RawDom(
                title=payload.title,
                url=payload.url,
                visible_text=payload.visible_text,
                elements=tuple(DomElement(**element.model_dump()) for element in payload.elements),
            ),
            raw_screenshot=RawScreenshot(payload.screenshot_data_url) if payload.screenshot_data_url else None,
        )
        return loop.step(observation, payload.user_instruction, approved_by_user=payload.approved_by_user)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("runtime.server:app", host="127.0.0.1", port=8000)
