from __future__ import annotations

import json
from dataclasses import dataclass

from agent.hf import HuggingFaceClient
from agent.ollama import OllamaClient
from runtime.state import ActionRequest, BrowserAction, SanitizedState


@dataclass
class Planner:
    ollama: OllamaClient | None = None
    hf_client: HuggingFaceClient | None = None

    def plan(self, state: SanitizedState, user_instruction: str, screenshot_b64: str | None = None) -> ActionRequest:
        if getattr(state, "_sanitized_marker", None) != "SANITIZED_STATE":
            raise TypeError("Planner only accepts SanitizedState")
        
        # 1. Try Ollama VLM
        if self.ollama and screenshot_b64 and self.ollama.check_vision_available():
            try:
                vision_analysis = self.ollama.analyze_screenshot(screenshot_b64, state, user_instruction)
                if vision_analysis.get("recommended_action"):
                    action_str = vision_analysis["recommended_action"]
                    if not action_str.startswith("browser."):
                        action_str = f"browser.{action_str}"
                    return ActionRequest(
                        action=BrowserAction(action_str),
                        element_id=vision_analysis.get("recommended_element_id"),
                        reasoning=vision_analysis.get("reasoning", "VLM proposed an action based on screenshot.")
                    )
            except Exception:
                pass
                
        # 2. Try Ollama text-only
        if self.ollama:
            try:
                return self._from_model(self.ollama.generate_json(state, user_instruction))
            except Exception:
                pass
                
        # 3. Try HuggingFace fallback
        if self.hf_client and self.hf_client.is_available():
            try:
                return self._from_hf(state, user_instruction)
            except Exception:
                pass
                
        # 4. Deterministic fallback
        return self._deterministic_fallback(state, user_instruction)

    def _from_hf(self, state: SanitizedState, user_instruction: str) -> ActionRequest:
        prompt = f"Goal: {user_instruction}\nElements: {json.dumps(list(state.elements))}\nRespond with JSON action."
        response_text = self.hf_client.generate_text(prompt)
        try:
            payload = json.loads(response_text)
            return self._from_model(payload)
        except Exception:
            return ActionRequest(BrowserAction.DONE, reasoning="HF model failed to return valid action JSON.")

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
            elem_id = str(element.get("id") or "").lower()
            elem_type = str(element.get("type") or "").lower()

            if "settings" in wanted and "settings" in label:
                return ActionRequest(BrowserAction.CLICK, element_id=str(element["id"]), reasoning="Clicked matching Settings control from sanitized DOM.")
            if "search" in wanted and ("search" in label or elem_type in {"input", "textbox"}):
                return ActionRequest(BrowserAction.TYPE, element_id=str(element["id"]), text=user_instruction, reasoning="Typed goal into sanitized search-like element.")
            if ("email" in wanted or "mail" in wanted or "write" in wanted or "send" in wanted):
                if "send" in label or "compose" in label or "submit" in label:
                    return ActionRequest(BrowserAction.CLICK, element_id=str(element["id"]), reasoning="Clicked email action button from sanitized DOM.")
                if ("recipient" in label or "email" in label or "subject" in label or "message" in label or "body" in label or elem_type in {"textarea", "input"}):
                    return ActionRequest(BrowserAction.TYPE, element_id=str(element["id"]), text="Hello from Privacy Agent", reasoning="Typed text into email input field.")
        return ActionRequest(BrowserAction.DONE, reasoning="No safe matching action found in sanitized state.")


