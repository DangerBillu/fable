from __future__ import annotations

import base64
import io
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageDraw

from runtime.state import ClassificationLevel, SensitiveCategory, SensitiveRegion, FaceRegion, VisualFinding


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
            if region.category == SensitiveCategory.FACE or self._is_oversized(region.bbox, image.width, image.height):
                continue
            x, y, w, h = self._padded_box(region.bbox, image.width, image.height)
            if region.category in HIGH_RISK or region.classification in {ClassificationLevel.RESTRICTED, ClassificationLevel.SECRET}:
                draw.rectangle((x, y, x + w, y + h), fill=(0, 0, 0))
            else:
                crop = image.crop((x, y, x + w, y + h)).filter(ImageFilter.GaussianBlur(radius=12))
                image.paste(crop, (x, y))
        buf = io.BytesIO()
        image.save(buf, format="WEBP", quality=80)
        return base64.b64encode(buf.getvalue()).decode("ascii"), image.width, image.height

    def blur_faces(self, image: Image.Image, face_regions: tuple[FaceRegion, ...]) -> int:
        count = 0
        for region in face_regions:
            if self._is_oversized((region.x, region.y, region.width, region.height), image.width, image.height):
                continue
            x, y, w, h = self._padded_box((region.x, region.y, region.width, region.height), image.width, image.height)
            crop = image.crop((x, y, x + w, y + h)).filter(ImageFilter.GaussianBlur(radius=20))
            image.paste(crop, (x, y))
            count += 1
        return count

    def redact_visual_findings(self, image: Image.Image, findings: tuple[VisualFinding, ...]) -> int:
        draw = ImageDraw.Draw(image)
        count = 0
        for finding in findings:
            if not finding.bbox:
                continue
            if self._is_oversized(finding.bbox, image.width, image.height):
                continue
            x, y, w, h = self._padded_box(finding.bbox, image.width, image.height)
            if finding.category == SensitiveCategory.QR_CODE:
                draw.rectangle((x, y, x + w, y + h), fill=(0, 0, 0))
            else:
                crop = image.crop((x, y, x + w, y + h)).filter(ImageFilter.GaussianBlur(radius=15))
                image.paste(crop, (x, y))
            count += 1
        return count

    def redact_full(self, data_url: str, text_regions: tuple[SensitiveRegion, ...], face_regions: tuple[FaceRegion, ...], visual_findings: tuple[VisualFinding, ...]) -> tuple[str, int, int, int]:
        image = self._load_data_url(data_url)
        draw = ImageDraw.Draw(image)
        total_redactions = 0
        
        for region in text_regions:
            if region.category == SensitiveCategory.FACE or self._is_oversized(region.bbox, image.width, image.height):
                continue
            x, y, w, h = self._padded_box(region.bbox, image.width, image.height)
            if region.category in HIGH_RISK or region.classification in {ClassificationLevel.RESTRICTED, ClassificationLevel.SECRET}:
                draw.rectangle((x, y, x + w, y + h), fill=(0, 0, 0))
            else:
                crop = image.crop((x, y, x + w, y + h)).filter(ImageFilter.GaussianBlur(radius=12))
                image.paste(crop, (x, y))
            total_redactions += 1
            
        total_redactions += self.blur_faces(image, face_regions)
        total_redactions += self.redact_visual_findings(image, visual_findings)
        
        buf = io.BytesIO()
        image.save(buf, format="WEBP", quality=80)
        return base64.b64encode(buf.getvalue()).decode("ascii"), image.width, image.height, total_redactions

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

    def _is_oversized(self, bbox: tuple[int, int, int, int], width: int, height: int) -> bool:
        _x, _y, w, h = bbox
        if w <= 0 or h <= 0:
            return True
        return (w * h) / max(width * height, 1) > 0.45
