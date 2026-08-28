from __future__ import annotations

import re
from dataclasses import dataclass

from runtime.state import ClassificationLevel, DomElement, SensitiveCategory, SensitiveFinding, SensitiveRegion
from runtime.tokenization import TokenVault


@dataclass(frozen=True)
class PatternRule:
    category: SensitiveCategory
    classification: ClassificationLevel
    regex: re.Pattern[str]
    confidence: float


PATTERN_RULES = (
    PatternRule(SensitiveCategory.EMAIL, ClassificationLevel.CONFIDENTIAL, re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), 0.99),
    PatternRule(SensitiveCategory.PHONE, ClassificationLevel.CONFIDENTIAL, re.compile(r"(?<!\d)(?:\+?\d[\s().-]*){7,}\d(?!\d)"), 0.9),
    PatternRule(SensitiveCategory.CREDIT_CARD, ClassificationLevel.RESTRICTED, re.compile(r"\b(?:\d[ -]*?){13,19}\b"), 0.98),
    PatternRule(SensitiveCategory.JWT, ClassificationLevel.SECRET, re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"), 0.99),
    PatternRule(SensitiveCategory.API_KEY, ClassificationLevel.SECRET, re.compile(r"\b(?:sk|pk|api)[-_][A-Za-z0-9][A-Za-z0-9._-]{8,}\b", re.I), 0.92),
    PatternRule(SensitiveCategory.AUTH_HEADER, ClassificationLevel.SECRET, re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.I), 0.99),
    PatternRule(SensitiveCategory.PRIVATE_KEY, ClassificationLevel.SECRET, re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), 1.0),
    PatternRule(SensitiveCategory.IDENTIFICATION_NUMBER, ClassificationLevel.RESTRICTED, re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), 0.95),
)

SENSITIVE_FIELD_RE = re.compile(
    r"password|passwd|pwd|email|e-mail|phone|tel|address|credit|card|cc-|cvc|cvv|ssn|social|dob|birth|api[_-]?key|token|secret|otp|one-time-code|auth",
    re.I,
)

HIGH_RISK_AUTOCOMPLETE = {
    "current-password",
    "new-password",
    "password",
    "cc-number",
    "cc-csc",
    "one-time-code",
}


class PrivacyDetector:
    def __init__(self, vault: TokenVault) -> None:
        self.vault = vault

    def inspect_dom_element(self, element: DomElement) -> tuple[DomElement, tuple[SensitiveFinding, ...], tuple[SensitiveRegion, ...]]:
        findings: list[SensitiveFinding] = []
        regions: list[SensitiveRegion] = []
        field_category = self._sensitive_field_category(element)

        value = element.value or ""
        text = element.text or ""
        placeholder = element.placeholder or ""
        label = " ".join(part for part in [element.aria_label, placeholder, text] if part)

        if field_category:
            token = self.vault.tokenize(field_category, value) if value else f"{field_category.value}_FIELD"
            if value:
                findings.append(SensitiveFinding(field_category, self._classification_for(field_category), value, 1.0, "dom", token, self._bbox(element)))
            if element.bbox:
                regions.append(SensitiveRegion(field_category, self._classification_for(field_category), self._bbox(element), 1.0, "dom", token))
            return self._redacted_element(element, token), tuple(findings), tuple(regions)

        sanitized_text, text_findings = self.inspect_text(text, "dom")
        sanitized_placeholder, placeholder_findings = self.inspect_text(placeholder, "dom")
        sanitized_label, label_findings = self.inspect_text(label, "dom")
        findings.extend(text_findings)
        findings.extend(placeholder_findings)
        findings.extend(label_findings)

        sanitized = DomElement(
            id=element.id,
            tag=element.tag,
            role=element.role,
            aria_label=sanitized_label or element.aria_label,
            text=sanitized_text,
            input_type=element.input_type,
            placeholder=sanitized_placeholder,
            autocomplete=element.autocomplete,
            bbox=element.bbox,
            enabled=element.enabled,
            href=self._safe_href(element.href),
            value=None,
            metadata={k: v for k, v in element.metadata.items() if k not in {"raw", "value", "innerHTML"}},
        )
        return sanitized, tuple(findings), tuple(regions)

    def inspect_text(self, text: str, source: str = "rules") -> tuple[str, tuple[SensitiveFinding, ...]]:
        sanitized = text or ""
        findings: list[SensitiveFinding] = []
        for rule in PATTERN_RULES:
            matches = list(rule.regex.finditer(sanitized))
            for match in matches:
                raw = match.group(0)
                token = self.vault.tokenize(rule.category, raw)
                findings.append(SensitiveFinding(rule.category, rule.classification, raw, rule.confidence, source, token))
                sanitized = sanitized.replace(raw, token)
        if self._looks_like_private_document(sanitized):
            token = self.vault.tokenize(SensitiveCategory.PRIVATE_DOCUMENT, sanitized[:512])
            findings.append(
                SensitiveFinding(
                    SensitiveCategory.PRIVATE_DOCUMENT,
                    ClassificationLevel.RESTRICTED,
                    sanitized[:512],
                    0.75,
                    source,
                    token,
                )
            )
            sanitized = "[PRIVATE_DOCUMENT_REDACTED]"
        return sanitized, tuple(findings)

    def _sensitive_field_category(self, element: DomElement) -> SensitiveCategory | None:
        haystack = " ".join(
            part
            for part in [
                element.input_type,
                element.autocomplete,
                element.aria_label,
                element.placeholder,
                element.id,
                element.metadata.get("name"),
            ]
            if part
        )
        input_type = (element.input_type or "").lower()
        autocomplete = (element.autocomplete or "").lower()
        if input_type == "password" or autocomplete in HIGH_RISK_AUTOCOMPLETE:
            return SensitiveCategory.PASSWORD
        if SENSITIVE_FIELD_RE.search(haystack):
            if "email" in haystack.lower():
                return SensitiveCategory.EMAIL
            if "phone" in haystack.lower() or "tel" in haystack.lower():
                return SensitiveCategory.PHONE
            if "credit" in haystack.lower() or "card" in haystack.lower() or "cc-" in haystack.lower():
                return SensitiveCategory.CREDIT_CARD
            if "token" in haystack.lower() or "secret" in haystack.lower() or "api" in haystack.lower():
                return SensitiveCategory.ACCESS_TOKEN
            return SensitiveCategory.UNKNOWN_SENSITIVE
        return None

    def _redacted_element(self, element: DomElement, token: str) -> DomElement:
        return DomElement(
            id=element.id,
            tag=element.tag,
            role=element.role,
            aria_label=element.aria_label,
            text=token if element.text else "",
            input_type=element.input_type,
            placeholder=token if element.placeholder else "",
            autocomplete=element.autocomplete,
            bbox=element.bbox,
            enabled=element.enabled,
            href=self._safe_href(element.href),
            value=None,
            metadata={k: v for k, v in element.metadata.items() if k not in {"raw", "value", "innerHTML"}},
        )

    def _classification_for(self, category: SensitiveCategory) -> ClassificationLevel:
        if category in {
            SensitiveCategory.PASSWORD,
            SensitiveCategory.CREDIT_CARD,
            SensitiveCategory.API_KEY,
            SensitiveCategory.ACCESS_TOKEN,
            SensitiveCategory.JWT,
            SensitiveCategory.AUTH_HEADER,
            SensitiveCategory.PRIVATE_KEY,
            SensitiveCategory.SECRET,
        }:
            return ClassificationLevel.SECRET
        if category in {SensitiveCategory.BANK_ACCOUNT, SensitiveCategory.IDENTIFICATION_NUMBER, SensitiveCategory.PRIVATE_DOCUMENT}:
            return ClassificationLevel.RESTRICTED
        return ClassificationLevel.CONFIDENTIAL

    def _safe_href(self, href: str | None) -> str | None:
        if not href:
            return None
        if href.startswith(("javascript:", "data:", "file:")):
            return None
        sanitized, _ = self.inspect_text(href, "rules")
        return sanitized

    def _bbox(self, element: DomElement) -> tuple[int, int, int, int]:
        if not element.bbox:
            return (0, 0, 0, 0)
        x, y, w, h = element.bbox
        return (int(x), int(y), int(w), int(h))

    def _looks_like_private_document(self, text: str) -> bool:
        lowered = text.lower()
        signals = ("confidential", "restricted", "internal memo", "nda", "privileged", "medical record", "bank statement")
        return sum(1 for signal in signals if signal in lowered) >= 2

