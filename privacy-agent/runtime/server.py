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
from runtime.perception import TelemetryExtractor
from runtime.policy import PolicyEngine
from runtime.privacy import FaceDetector, ImageRedactor, PrivacyDetector, PrivacyFirewall, VisualClassifier
from runtime.state import DomElement, FaceRegion, RawDom, RawObservation, RawScreenshot
from runtime.tokenization import TokenVault

# Optional: import HuggingFace client
try:
    from agent.hf import HuggingFaceClient
except ImportError:
    HuggingFaceClient = None


class FaceRegionPayload(BaseModel):
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.75
    source: str = "browser"


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
    face_regions: list[FaceRegionPayload] = Field(default_factory=list)


vault = TokenVault()
app = FastAPI(title="Privacy Agent Runtime", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1", "http://localhost", "chrome-extension://*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build HuggingFace client if token is available
hf_client = None
hf_token = os.getenv("HF_API_TOKEN", "")
if hf_token and HuggingFaceClient:
    hf_client = HuggingFaceClient(
        api_token=hf_token,
        vision_model=os.getenv("HF_VISION_MODEL", "Salesforce/blip2-opt-2.7b"),
        text_model=os.getenv("HF_TEXT_MODEL", "mistralai/Mistral-7B-Instruct-v0.3"),
    )

# Build agent loop with all components
face_detector = FaceDetector() if os.getenv("FACE_DETECTION", "1") == "1" else None
visual_classifier = VisualClassifier()
ollama_client = OllamaClient() if os.getenv("USE_OLLAMA", "0") == "1" else None

loop = AgentLoop(
    firewall=PrivacyFirewall(
        detector=PrivacyDetector(vault),
        redactor=ImageRedactor(),
        face_detector=face_detector,
        visual_classifier=visual_classifier,
        telemetry_extractor=TelemetryExtractor(),
        mode=os.getenv("PRIVACY_MODE", "STRICT"),
    ),
    planner=Planner(ollama=ollama_client, hf_client=hf_client),
    policy=PolicyEngine(mode=os.getenv("PRIVACY_MODE", "STRICT")),
    gateway=McpGateway(vault),
    audit=AuditLogger(ROOT / "audit.log"),
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "privacy": "local-only", "version": "0.2.0"}


@app.get("/health/vision")
def health_vision() -> dict[str, Any]:
    """Check if Ollama VLM is available."""
    vlm_available = False
    if ollama_client:
        vlm_available = ollama_client.check_vision_available()
    return {
        "vlm_available": vlm_available,
        "vision_model": os.getenv("VISION_MODEL", "llava"),
        "ollama_enabled": ollama_client is not None,
    }


@app.get("/health/hf")
def health_hf() -> dict[str, Any]:
    """Check if HuggingFace API is reachable."""
    hf_available = False
    if hf_client:
        hf_available = hf_client.is_available()
    return {
        "hf_available": hf_available,
        "hf_token_set": bool(hf_token),
    }


@app.post("/agent/step")
def agent_step(payload: ObservationPayload) -> dict:
    try:
        face_regions = tuple(
            FaceRegion(
                x=fr.x,
                y=fr.y,
                width=fr.width,
                height=fr.height,
                confidence=fr.confidence,
                source=fr.source,
            )
            for fr in payload.face_regions
        )
        observation = RawObservation(
            session_id=payload.session_id,
            raw_dom=RawDom(
                title=payload.title,
                url=payload.url,
                visible_text=payload.visible_text,
                elements=tuple(DomElement(**element.model_dump()) for element in payload.elements),
            ),
            raw_screenshot=RawScreenshot(payload.screenshot_data_url) if payload.screenshot_data_url else None,
            face_regions=face_regions,
        )
        return loop.step(observation, payload.user_instruction, approved_by_user=payload.approved_by_user)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", os.getenv("RUNTIME_PORT", "8000")))
    uvicorn.run(app, host="127.0.0.1", port=port)

