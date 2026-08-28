from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from runtime.schemas import observation_to_json
from runtime.state import SanitizedObservation


@dataclass
class ContextBuilder:
    available_actions: tuple[str, ...] = (
        "browser.click",
        "browser.type",
        "browser.scroll",
        "browser.navigate",
        "browser.go_back",
        "browser.wait",
        "browser.done",
        "raise_alert",
        "pause_simulation",
        "collect_safe_data",
        "notify_operator",
    )

    def build(self, observation: SanitizedObservation, user_instruction: str, temporal_update: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "trust_boundary": "raw_pixels_and_raw_ocr_excluded",
            "instruction": user_instruction,
            "observation": observation_to_json(observation),
            "temporal_update": temporal_update,
            "permissions": {
                "raw_screenshot_access": False,
                "raw_ocr_access": False,
                "shell_access": False,
                "requires_policy_validation": True,
            },
            "available_actions": list(self.available_actions),
        }
