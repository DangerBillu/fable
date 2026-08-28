from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class SensitiveCategory(str, Enum):
    PASSWORD = "PASSWORD"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    CREDIT_CARD = "CREDIT_CARD"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    API_KEY = "API_KEY"
    ACCESS_TOKEN = "ACCESS_TOKEN"
    JWT = "JWT"
    AUTH_HEADER = "AUTH_HEADER"
    PRIVATE_KEY = "PRIVATE_KEY"
    SECRET = "SECRET"
    ADDRESS = "ADDRESS"
    PERSONAL_NAME = "PERSONAL_NAME"
    IDENTIFICATION_NUMBER = "IDENTIFICATION_NUMBER"
    PRIVATE_DOCUMENT = "PRIVATE_DOCUMENT"
    QR_CODE = "QR_CODE"
    FACE = "FACE"
    UNKNOWN_SENSITIVE = "UNKNOWN_SENSITIVE"


class ClassificationLevel(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"
    SECRET = "SECRET"


class BrowserAction(str, Enum):
    GET_PAGE = "browser.get_page"
    GET_DOM = "browser.get_dom"
    GET_SCREENSHOT = "browser.get_screenshot"
    CLICK = "browser.click"
    TYPE = "browser.type"
    SCROLL = "browser.scroll"
    PRESS_KEY = "browser.press_key"
    NAVIGATE = "browser.navigate"
    SELECT = "browser.select"
    GO_BACK = "browser.go_back"
    WAIT = "browser.wait"
    DONE = "browser.done"


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass(frozen=True)
class RawScreenshot:
    data_url: str


@dataclass(frozen=True)
class DomElement:
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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RawDom:
    title: str
    url: str
    elements: tuple[DomElement, ...]
    visible_text: str = ""


@dataclass(frozen=True)
class FaceRegion:
    """A detected face bounding box, from browser-side or server-side detection."""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    source: Literal["browser", "server"] = "server"


@dataclass(frozen=True)
class VisualFinding:
    """A visual content classification result from image analysis."""
    category: SensitiveCategory
    classification: ClassificationLevel
    description: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None
    source: Literal["opencv", "heuristic", "huggingface"] = "opencv"


@dataclass(frozen=True)
class RawObservation:
    session_id: str
    raw_dom: RawDom
    raw_screenshot: RawScreenshot | None = None
    raw_ocr_text: str | None = None
    face_regions: tuple[FaceRegion, ...] = ()



@dataclass(frozen=True)
class SensitiveRegion:
    category: SensitiveCategory
    classification: ClassificationLevel
    bbox: tuple[int, int, int, int]
    confidence: float
    source: Literal["dom", "ocr", "rules", "vision", "heuristic"]
    token: str | None = None


@dataclass(frozen=True)
class SensitiveFinding:
    category: SensitiveCategory
    classification: ClassificationLevel
    raw_value: str
    confidence: float
    source: Literal["dom", "ocr", "rules", "vision", "heuristic"]
    token: str | None = None
    bbox: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class SanitizedScreenshot:
    webp_base64: str
    width: int
    height: int
    redaction_count: int


@dataclass(frozen=True)
class SanitizedDom:
    title: str
    domain: str
    elements: tuple[DomElement, ...]
    visible_text: str
    url: str = ""


@dataclass(frozen=True)
class SanitizedState:
    page: dict[str, Any]
    elements: tuple[dict[str, Any], ...]
    visible_text: str
    privacy: dict[str, Any]
    telemetry: dict[str, Any] = field(default_factory=dict)
    ui_state: dict[str, Any] = field(default_factory=dict)
    _sanitized_marker: Literal["SANITIZED_STATE"] = "SANITIZED_STATE"


@dataclass(frozen=True)
class SanitizedObservation:
    session_id: str
    sanitized_dom: SanitizedDom
    sanitized_screenshot: SanitizedScreenshot | None
    sensitive_regions: tuple[SensitiveRegion, ...]
    sensitive_findings: tuple[SensitiveFinding, ...]
    state: SanitizedState
    face_count: int = 0
    visual_findings_count: int = 0


@dataclass(frozen=True)
class ActionRequest:
    action: BrowserAction
    element_id: str | None = None
    text: str | None = None
    url: str | None = None
    key: str | None = None
    value: str | None = None
    delta_x: int | None = None
    delta_y: int | None = None
    reasoning: str = ""


@dataclass(frozen=True)
class ApprovedAction:
    request: ActionRequest
    decision: PolicyDecision
    approval_id: str | None = None
