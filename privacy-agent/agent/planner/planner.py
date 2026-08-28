from __future__ import annotations

from dataclasses import dataclass

from agent.ollama import OllamaClient
from runtime.state import ActionRequest, BrowserAction, SanitizedState


@dataclass
class Planner:
    ollama: OllamaClient | None = None

    def plan(self, state: SanitizedState, user_instruction: str) -> ActionRequest:
        if getattr(state, "_sanitized_marker", None) != "SANITIZED_STATE":
            raise TypeError("Planner only accepts SanitizedState")
        if self.ollama:
            try:
                return self._from_model(self.ollama.generate_json(state, user_instruction))
            except Exception:
                pass
        return self._deterministic_fallback(state, user_instruction)

    def _from_model(self, payload: dict) -> ActionRequest:
        action = BrowserAction(payload["action"])
        return ActionRequest(
            action=action,
            element_id=payload.get("element_id"),
            text=payload.get("text"),
            url=payload.get("url"),
            key=payload.get("key"),
            value=payload.get("value"),
            delta_x=payload.get("delta_x"),
            delta_y=payload.get("delta_y"),
            reasoning=payload.get("reasoning", "Model proposed a structured action."),
        )

    def _deterministic_fallback(self, state: SanitizedState, user_instruction: str) -> ActionRequest:
        wanted = user_instruction.lower()
        for element in state.elements:
            label = str(element.get("label") or "").lower()
            if "settings" in wanted and "settings" in label:
                return ActionRequest(BrowserAction.CLICK, element_id=str(element["id"]), reasoning="Clicked matching Settings control from sanitized DOM.")
            if "search" in wanted and ("search" in label or element.get("type") in {"input", "textbox"}):
                return ActionRequest(BrowserAction.TYPE, element_id=str(element["id"]), text=user_instruction, reasoning="Typed goal into sanitized search-like element.")
        return ActionRequest(BrowserAction.DONE, reasoning="No safe matching action found in sanitized state.")

