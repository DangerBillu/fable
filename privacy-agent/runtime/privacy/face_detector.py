from __future__ import annotations

import logging
import os

try:
    import cv2
    import numpy as np
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

from runtime.state.types import FaceRegion

logger = logging.getLogger(__name__)


class FaceDetector:
    """Server-side face detection using OpenCV.

    Supports both OpenCV 5.x (FaceDetectorYN with DNN) and OpenCV 4.x
    (CascadeClassifier with Haar cascades). Falls back gracefully if
    neither is available.
    """

    def __init__(self, confidence_threshold: float = 0.75) -> None:
        self._detector = None
        self._cascade = None
        self._confidence_threshold = confidence_threshold

        if not HAS_OPENCV:
            logger.warning("OpenCV not installed - server-side face detection disabled")
            return

        # Try OpenCV 5.x FaceDetectorYN (DNN-based, more accurate)
        if hasattr(cv2, "FaceDetectorYN_create"):
            try:
                model_path = os.path.join(
                    os.path.dirname(cv2.__file__),
                    "data",
                    "face_detection_yunet_2023mar.onnx",
                )
                if os.path.exists(model_path):
                    self._detector = cv2.FaceDetectorYN_create(
                        model_path, "", (320, 320), confidence_threshold
                    )
                    logger.info("Using FaceDetectorYN (DNN) for face detection")
                    return
            except Exception as exc:
                logger.debug("FaceDetectorYN init failed: %s", exc)

        # Try OpenCV 4.x CascadeClassifier (Haar cascades)
        if hasattr(cv2, "CascadeClassifier"):
            try:
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                self._cascade = cv2.CascadeClassifier(cascade_path)
                if not self._cascade.empty():
                    logger.info("Using Haar CascadeClassifier for face detection")
                    return
                self._cascade = None
            except Exception as exc:
                logger.debug("CascadeClassifier init failed: %s", exc)
                self._cascade = None

        logger.info("Server-side face detection fallback initialized (browser-side detection active)")


    def detect_faces(self, image_bytes: bytes) -> list[FaceRegion]:
        """Detect faces in an image. Returns list of FaceRegion objects."""
        if not HAS_OPENCV:
            return []

        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return []

            # FaceDetectorYN (OpenCV 5.x)
            if self._detector is not None:
                return self._detect_with_dnn(img)

            # CascadeClassifier (OpenCV 4.x)
            if self._cascade is not None:
                return self._detect_with_cascade(img)

            return []
        except Exception as exc:
            logger.error("Error during face detection: %s", exc)
            return []

    def _detect_with_dnn(self, img: np.ndarray) -> list[FaceRegion]:
        """Detect faces using FaceDetectorYN (DNN)."""
        h, w = img.shape[:2]
        self._detector.setInputSize((w, h))
        _, faces = self._detector.detect(img)
        if faces is None:
            return []
        regions = []
        for face in faces:
            x, y, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            conf = float(face[14]) if face.shape[0] > 14 else 0.85
            if conf >= self._confidence_threshold:
                regions.append(
                    FaceRegion(x=x, y=y, width=fw, height=fh, confidence=conf, source="server")
                )
        return regions

    def _detect_with_cascade(self, img: np.ndarray) -> list[FaceRegion]:
        """Detect faces using Haar CascadeClassifier."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        regions = []
        for x, y, w, h in faces:
            regions.append(
                FaceRegion(x=int(x), y=int(y), width=int(w), height=int(h), confidence=0.85, source="server")
            )
        return regions

    def merge_face_regions(
        self,
        browser_regions: tuple[FaceRegion, ...],
        server_regions: list[FaceRegion],
        iou_threshold: float = 0.5,
    ) -> list[FaceRegion]:
        """Merge browser-detected and server-detected faces, deduplicating by IoU."""
        merged = list(browser_regions)

        for s_reg in server_regions:
            is_duplicate = False
            for b_reg in merged:
                if self._compute_iou(s_reg, b_reg) > iou_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                merged.append(s_reg)

        return merged

    @staticmethod
    def _compute_iou(a: FaceRegion, b: FaceRegion) -> float:
        """Compute Intersection over Union between two face regions."""
        x_overlap = max(0, min(a.x + a.width, b.x + b.width) - max(a.x, b.x))
        y_overlap = max(0, min(a.y + a.height, b.y + b.height) - max(a.y, b.y))
        intersection = x_overlap * y_overlap
        if intersection == 0:
            return 0.0
        union = (a.width * a.height) + (b.width * b.height) - intersection
        return intersection / union if union > 0 else 0.0
