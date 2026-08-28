from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from runtime.privacy.detectors import PrivacyDetector
from runtime.privacy.redactor import ImageRedactor
from runtime.state import (
    ClassificationLevel,
    DomElement,
    RawObservation,
    SanitizedDom,
    SanitizedObservation,
    SanitizedScreenshot,
    SanitizedState,
    SensitiveFinding,
    SensitiveRegion,
)


@dataclass
class PrivacyFirewall:
    detector: PrivacyDetector
    redactor: ImageRedactor
    mode: str = "STRICT"

    def sanitize(self, observation: RawObservation) -> SanitizedObservation:
        sanitized_elements: list[DomElement] = []
        findings: list[SensitiveFinding] = []
        regions: list[SensitiveRegion] = []

        for element in observation.raw_dom.elements:
            sanitized, element_findings, element_regions = self.detector.inspect_dom_element(element)
            sanitized_elements.append(sanitized)
            findings.extend(element_findings)
            regions.extend(element_regions)

        visible_text, visible_findings = self.detector.inspect_text(observation.raw_dom.visible_text, "dom")
        findings.extend(visible_findings)
        if observation.raw_ocr_text:
            ocr_text, ocr_findings = self.detector.inspect_text(observation.raw_ocr_text, "ocr")
            visible_text = "\n".join(part for part in [visible_text, ocr_text] if part)
            findings.extend(ocr_findings)

        screenshot = None
        if observation.raw_screenshot:
            try:
                image, width, height = self.redactor.redact_data_url(observation.raw_screenshot.data_url, tuple(regions))
                screenshot = SanitizedScreenshot(image, width, height, len(regions))
            except Exception:
                if self.mode.upper() == "DEBUG":
                    raise
                screenshot = None
                findings.append(
                    SensitiveFinding(
                        category=self._unknown_category(),
                        classification=ClassificationLevel.SECRET,
                        raw_value="[SCREENSHOT_REDACTION_FAILED]",
                        confidence=1.0,
                        source="heuristic",
                        token=None,
                    )
                )

        domain = urlparse(observation.raw_dom.url).hostname or "unknown"
        sanitized_dom = SanitizedDom(
            title=visible_safe_title(observation.raw_dom.title),
            domain=domain,
            elements=tuple(sanitized_elements),
            visible_text=visible_text,
        )
        state = self._state_from_dom(sanitized_dom, findings, regions, screenshot)
        assert state._sanitized_marker == "SANITIZED_STATE"
        return SanitizedObservation(
            session_id=observation.session_id,
            sanitized_dom=sanitized_dom,
            sanitized_screenshot=screenshot,
            sensitive_regions=tuple(regions),
            sensitive_findings=tuple(findings),
            state=state,
        )

    def _state_from_dom(
        self,
        dom: SanitizedDom,
        findings: list[SensitiveFinding],
        regions: list[SensitiveRegion],
        screenshot: SanitizedScreenshot | None,
    ) -> SanitizedState:
        return SanitizedState(
            page={"title": dom.title, "domain": dom.domain},
            elements=tuple(
                {
                    "id": element.id,
                    "type": element.role or element.tag,
                    "label": first_nonempty(element.aria_label, element.text, element.placeholder),
                    "bbox": element.bbox,
                    "enabled": element.enabled,
                    "href": element.href,
                }
                for element in dom.elements
            ),
            visible_text=dom.visible_text,
            privacy={
                "mode": self.mode,
                "findings": len(findings),
                "sensitive_regions": len(regions),
                "redacted": screenshot.redaction_count if screenshot else 0,
                "categories": sorted({finding.category.value for finding in findings}),
                "raw_data_local_only": True,
            },
        )

    def _unknown_category(self):
        from runtime.state import SensitiveCategory

        return SensitiveCategory.UNKNOWN_SENSITIVE


def first_nonempty(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def visible_safe_title(title: str) -> str:
    return title.replace("\n", " ").strip()[:120]

