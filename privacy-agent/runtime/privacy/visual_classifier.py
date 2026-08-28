import logging
from typing import List

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

from runtime.state.types import VisualFinding, SensitiveCategory, ClassificationLevel

logger = logging.getLogger(__name__)

class VisualClassifier:
    def __init__(self):
        self.qr_detector = None
        if HAS_OPENCV:
            self.qr_detector = cv2.QRCodeDetector()

    def classify(self, image_bytes: bytes) -> list[VisualFinding]:
        if not HAS_OPENCV:
            logger.warning("OpenCV not available, skipping visual classification")
            return []
            
        findings = []
        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return []
                
            if self.qr_detector is not None:
                retval, decoded_info, points, straight_qrcode = self.qr_detector.detectAndDecodeMulti(img)
                if retval and points is not None:
                    for i, pts in enumerate(points):
                        x_coords = pts[:, 0]
                        y_coords = pts[:, 1]
                        x, y = int(np.min(x_coords)), int(np.min(y_coords))
                        w, h = int(np.max(x_coords) - x), int(np.max(y_coords) - y)
                        findings.append(VisualFinding(
                            category=SensitiveCategory.QR_CODE,
                            classification=ClassificationLevel.RESTRICTED,
                            description="Detected QR code",
                            confidence=0.9,
                            bbox=(x, y, w, h),
                            source="opencv"
                        ))

            # Detect document/ID card shapes
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edged = cv2.Canny(blurred, 75, 200)
            
            contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            img_area = img.shape[0] * img.shape[1]
            
            for c in contours:
                peri = cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                
                if len(approx) == 4:
                    area = cv2.contourArea(approx)
                    if img_area * 0.05 < area < img_area * 0.9:
                        x, y, w, h = cv2.boundingRect(approx)
                        findings.append(VisualFinding(
                            category=SensitiveCategory.PRIVATE_DOCUMENT,
                            classification=ClassificationLevel.RESTRICTED,
                            description="Detected document/ID card shape",
                            confidence=0.7,
                            bbox=(x, y, w, h),
                            source="heuristic"
                        ))
            
        except Exception as e:
            logger.error(f"Error during visual classification: {e}")
            
        return findings
