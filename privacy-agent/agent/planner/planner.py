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

            # Rocket launch simulation controls
            if "stage" in wanted or "separation" in wanted or "booster" in wanted:
                if "stage" in label or "separation" in label or "sep" in elem_id:
                    return ActionRequest(BrowserAction.CLICK, element_id=str(element["id"]), reasoning="Triggered Stage Separation on rocket launch console.")
            if "fairing" in wanted or "jettison" in wanted or "ogive" in wanted:
                if "fairing" in label or "jettison" in label or "fairing" in elem_id:
                    return ActionRequest(BrowserAction.CLICK, element_id=str(element["id"]), reasoning="Jettisoned Payload Fairing on rocket launch console.")
            if "gimbal" in wanted or "recalibrate" in wanted or "nozzle" in wanted or "pitch" in wanted:
                if "gimbal" in label or "recal" in elem_id:
                    return ActionRequest(BrowserAction.CLICK, element_id=str(element["id"]), reasoning="Recalibrated Engine Gimbal on rocket launch console.")
            if "hold" in wanted or "freeze" in wanted or "emergency" in wanted:
                if "hold" in label or "hold" in elem_id or "emergency" in label:
                    return ActionRequest(BrowserAction.CLICK, element_id=str(element["id"]), reasoning="Toggled Emergency Telemetry Hold on rocket launch console.")

            if "settings" in wanted and "settings" in label:
                return ActionRequest(BrowserAction.CLICK, element_id=str(element["id"]), reasoning="Clicked matching Settings control from sanitized DOM.")
            if "search" in wanted and ("search" in label or elem_type in {"input", "textbox"}):
                return ActionRequest(BrowserAction.TYPE, element_id=str(element["id"]), text=user_instruction, reasoning="Typed goal into sanitized search-like element.")
            # Email dispatch & test results communication
            if ("email" in wanted or "mail" in wanted or "report" in wanted or "test results" in wanted or "transmit" in wanted or "send" in wanted):
                # Extract target email address if mentioned in user instruction
                import re
                email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", user_instruction)
                target_email = email_match.group(0) if email_match else "mission-control@isro.gov.in"

                # Check if there is an email input field to type into
                if "telemetry-email-to" in elem_id or "email-to" in elem_id or ("recipient" in label and elem_type in {"input", "text", "email"}):
                    return ActionRequest(
                        BrowserAction.TYPE,
                        element_id=str(element["id"]),
                        text=target_email,
                        reasoning=f"Typed recipient address '{target_email}' into official telemetry email field."
                    )
                # Check for transmit / send button
                if "btn-send" in elem_id or "send-telemetry" in elem_id or "report" in elem_id or "transmit" in label or "send" in label:
                    return ActionRequest(
                        BrowserAction.CLICK,
                        element_id=str(element["id"]),
                        reasoning=f"Dispatched sanitized flight test telemetry report to {target_email}."
                    )
                if ("subject" in label or "message" in label or "body" in label or elem_type in {"textarea", "input"}):
                    return ActionRequest(
                        BrowserAction.TYPE,
                        element_id=str(element["id"]),
                        text="Flight Telemetry Nominal: Alt 54.2km, Vel 1824m/s, Mach 5.42. All classified specs redacted.",
                        reasoning="Populated telemetry report into email input field."
                    )
        return ActionRequest(BrowserAction.DONE, reasoning="No safe matching action found in sanitized state.")


