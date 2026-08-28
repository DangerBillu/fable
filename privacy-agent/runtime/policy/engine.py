from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

from runtime.state import ActionRequest, ApprovedAction, BrowserAction, PolicyDecision, SanitizedState


LOW_RISK = {BrowserAction.GET_PAGE, BrowserAction.GET_DOM, BrowserAction.GET_SCREENSHOT, BrowserAction.CLICK, BrowserAction.SCROLL, BrowserAction.PRESS_KEY, BrowserAction.GO_BACK, BrowserAction.WAIT, BrowserAction.DONE}
MEDIUM_RISK = {BrowserAction.TYPE, BrowserAction.SELECT, BrowserAction.NAVIGATE}
HIGH_RISK_KEYWORDS = ("delete", "remove", "transfer", "upload", "download", "permission", "share", "send")


@dataclass
class PolicyEngine:
    mode: str = "STRICT"
    allowed_domains: set[str] = field(default_factory=set)
    blocked_domains: set[str] = field(default_factory=set)
    disabled_tools: set[BrowserAction] = field(default_factory=set)
    require_approval_for_all: bool = False

    def evaluate(self, state: SanitizedState, request: ActionRequest, approved_by_user: bool = False) -> ApprovedAction:
        if getattr(state, "_sanitized_marker", None) != "SANITIZED_STATE":
            return ApprovedAction(request, PolicyDecision.DENY)
        if request.action in self.disabled_tools:
            return ApprovedAction(request, PolicyDecision.DENY)
        if request.action == BrowserAction.NAVIGATE and request.url:
            host = urlparse(request.url).hostname or ""
            if self._blocked(host):
                return ApprovedAction(request, PolicyDecision.DENY)
            if self.allowed_domains and not self._allowed(host):
                return ApprovedAction(request, PolicyDecision.REQUIRE_APPROVAL if not approved_by_user else PolicyDecision.ALLOW)
        if self.require_approval_for_all and not approved_by_user:
            return ApprovedAction(request, PolicyDecision.REQUIRE_APPROVAL)
        if request.action in LOW_RISK:
            return ApprovedAction(request, PolicyDecision.ALLOW)
        if request.action in MEDIUM_RISK:
            if self.mode.upper() == "STRICT" and not approved_by_user:
                return ApprovedAction(request, PolicyDecision.REQUIRE_APPROVAL)
            if request.text and self._contains_sensitive_token(request.text) and not approved_by_user:
                return ApprovedAction(request, PolicyDecision.REQUIRE_APPROVAL)
            return ApprovedAction(request, PolicyDecision.ALLOW)
        if any(word in request.reasoning.lower() for word in HIGH_RISK_KEYWORDS):
            return ApprovedAction(request, PolicyDecision.REQUIRE_APPROVAL if not approved_by_user else PolicyDecision.ALLOW)
        return ApprovedAction(request, PolicyDecision.DENY)

    def _blocked(self, host: str) -> bool:
        return any(host == domain or host.endswith("." + domain.lstrip("*.")) for domain in self.blocked_domains)

    def _allowed(self, host: str) -> bool:
        return any(host == domain or host.endswith("." + domain.lstrip("*.")) for domain in self.allowed_domains)

    def _contains_sensitive_token(self, text: str) -> bool:
        return any(prefix in text for prefix in ("PASSWORD_", "EMAIL_", "PHONE_", "CREDIT_CARD_", "API_KEY_", "ACCESS_TOKEN_", "JWT_"))

