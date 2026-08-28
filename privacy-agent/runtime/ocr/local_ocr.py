from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class LocalOcr:
    enabled: bool = True

    def extract_text_from_image(self, image: Image.Image) -> str:
        """Use local Tesseract CLI when present; otherwise fail closed upstream."""
        if not self.enabled:
            raise RuntimeError("OCR is disabled")
        if not shutil.which("tesseract"):
            raise RuntimeError("Local tesseract executable was not found")
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "screen.png"
            output = Path(tmp) / "ocr"
            image.save(source)
            subprocess.run(["tesseract", str(source), str(output), "--psm", "6"], check=True, capture_output=True)
            return output.with_suffix(".txt").read_text(encoding="utf-8", errors="replace")

