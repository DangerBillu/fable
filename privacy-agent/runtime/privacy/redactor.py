from __future__ import annotations

import base64
import io
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageDraw

from runtime.state import ClassificationLevel, SensitiveCategory, SensitiveRegion


HIGH_RISK = {
    SensitiveCategory.PASSWORD,
    SensitiveCategory.API_KEY,
    SensitiveCategory.ACCESS_TOKEN,
    SensitiveCategory.JWT,
    SensitiveCategory.AUTH_HEADER,
    SensitiveCategory.PRIVATE_KEY,
    SensitiveCategory.CREDIT_CARD,
    SensitiveCategory.SECRET,
}


@dataclass
class ImageRedactor:
    padding: int = 10

    def redact_data_url(self, data_url: str, regions: tuple[SensitiveRegion, ...]) -> tuple[str, int, int]:
        image = self._load_data_url(data_url)
        draw = ImageDraw.Draw(image)
        for region in regions:
            x, y, w, h = self._padded_box(region.bbox, image.width, image.height)
            if region.category in HIGH_RISK or region.classification in {ClassificationLevel.RESTRICTED, ClassificationLevel.SECRET}:
                draw.rectangle((x, y, x + w, y + h), fill=(0, 0, 0))
            else:
                crop = image.crop((x, y, x + w, y + h)).filter(ImageFilter.GaussianBlur(radius=12))
                image.paste(crop, (x, y))
        buf = io.BytesIO()
        image.save(buf, format="WEBP", quality=80)
        return base64.b64encode(buf.getvalue()).decode("ascii"), image.width, image.height

    def _load_data_url(self, data_url: str) -> Image.Image:
        if not data_url.startswith("data:image/"):
            raise ValueError("Expected screenshot as image data URL")
        _, payload = data_url.split(",", 1)
        raw = base64.b64decode(payload, validate=True)
        return Image.open(io.BytesIO(raw)).convert("RGB")

    def _padded_box(self, bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
        x, y, w, h = bbox
        left = max(0, x - self.padding)
        top = max(0, y - self.padding)
        right = min(width, x + w + self.padding)
        bottom = min(height, y + h + self.padding)
        return left, top, max(0, right - left), max(0, bottom - top)

