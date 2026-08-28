from __future__ import annotations

import os
import platform
from dataclasses import dataclass


@dataclass
class ResourceManager:
    def snapshot(self) -> dict[str, object]:
        memory = self._memory_bytes()
        return {
            "platform": platform.platform(),
            "cpu_cores": os.cpu_count() or 1,
            "ram_bytes": memory,
            "gpu_available": False,
            "recommendation": self._recommendation(memory),
        }

    def _memory_bytes(self) -> int | None:
        try:
            import psutil  # type: ignore

            return int(psutil.virtual_memory().total)
        except Exception:
            return None

    def _recommendation(self, memory: int | None) -> str:
        if not memory:
            return "Unknown RAM; default to small local models and avoid VLM unless required."
        gib = memory / (1024**3)
        if gib < 8:
            return "Use small reasoning models, DOM-first perception, OCR only when necessary, no resident VLM."
        if gib < 16:
            return "Use 7B-8B reasoning models and load vision models on demand."
        return "A larger local model may be usable, but keep privacy detection deterministic by default."

