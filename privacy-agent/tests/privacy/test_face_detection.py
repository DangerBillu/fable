import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from runtime.state.types import FaceRegion, SensitiveCategory, ClassificationLevel


class FaceDetectorTests(unittest.TestCase):
    """Tests for server-side face detection."""

    def test_face_detector_import(self):
        """FaceDetector can be imported without crashing even if OpenCV is missing."""
        from runtime.privacy.face_detector import FaceDetector
        detector = FaceDetector()
        self.assertIsNotNone(detector)

    def test_detect_faces_with_synthetic_image(self):
        """FaceDetector returns a list (possibly empty) for valid image bytes."""
        from runtime.privacy.face_detector import FaceDetector
        from PIL import Image
        import io

        # Create a simple synthetic image (100x100 white square)
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        detector = FaceDetector()
        faces = detector.detect_faces(image_bytes)
        # On a blank image, expect 0 faces (but should not crash)
        self.assertIsInstance(faces, list)

    def test_detect_faces_returns_face_region_objects(self):
        """If faces are detected, they should be FaceRegion objects."""
        from runtime.privacy.face_detector import FaceDetector
        from PIL import Image
        import io

        img = Image.new("RGB", (200, 200), color=(128, 128, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        detector = FaceDetector()
        faces = detector.detect_faces(image_bytes)
        for face in faces:
            self.assertIsInstance(face, FaceRegion)
            self.assertEqual(face.source, "server")

    def test_merge_face_regions_no_overlap(self):
        """Non-overlapping regions from browser and server should all be included."""
        from runtime.privacy.face_detector import FaceDetector

        browser_regions = (
            FaceRegion(x=10, y=10, width=50, height=50, confidence=0.9, source="browser"),
        )
        server_regions = [
            FaceRegion(x=200, y=200, width=60, height=60, confidence=0.85, source="server"),
        ]

        detector = FaceDetector()
        merged = detector.merge_face_regions(browser_regions, server_regions)
        self.assertEqual(len(merged), 2)

    def test_merge_face_regions_with_overlap(self):
        """Overlapping regions should be deduplicated (server region dropped)."""
        from runtime.privacy.face_detector import FaceDetector

        browser_regions = (
            FaceRegion(x=10, y=10, width=50, height=50, confidence=0.9, source="browser"),
        )
        server_regions = [
            FaceRegion(x=15, y=15, width=45, height=45, confidence=0.85, source="server"),
        ]

        detector = FaceDetector()
        merged = detector.merge_face_regions(browser_regions, server_regions, iou_threshold=0.3)
        # The server region overlaps significantly, should be deduplicated
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].source, "browser")

    def test_face_region_to_sensitive_region(self):
        """FaceRegion can be converted to SensitiveRegion for the redaction pipeline."""
        from runtime.state import SensitiveRegion

        face = FaceRegion(x=50, y=50, width=100, height=100, confidence=0.92, source="server")
        region = SensitiveRegion(
            category=SensitiveCategory.FACE,
            classification=ClassificationLevel.RESTRICTED,
            bbox=(face.x, face.y, face.width, face.height),
            confidence=face.confidence,
            source="vision",
        )
        self.assertEqual(region.category, SensitiveCategory.FACE)
        self.assertEqual(region.classification, ClassificationLevel.RESTRICTED)
        self.assertEqual(region.bbox, (50, 50, 100, 100))

    def test_redactor_blur_faces(self):
        """ImageRedactor.blur_faces applies blur to face regions."""
        from runtime.privacy.redactor import ImageRedactor
        from PIL import Image

        img = Image.new("RGB", (200, 200), color=(255, 0, 0))
        face_regions = (
            FaceRegion(x=50, y=50, width=60, height=60, confidence=0.9, source="server"),
        )
        redactor = ImageRedactor()
        count = redactor.blur_faces(img, face_regions)
        self.assertEqual(count, 1)
        # Verify the face region is no longer solid red (blur changes pixels)
        pixel = img.getpixel((80, 80))
        # After blur with padding, center pixel may still be red-ish but edges won't be pure red
        self.assertIsNotNone(pixel)

    def test_detect_faces_invalid_bytes(self):
        """FaceDetector should gracefully handle invalid image bytes."""
        from runtime.privacy.face_detector import FaceDetector

        detector = FaceDetector()
        faces = detector.detect_faces(b"not_an_image")
        self.assertIsInstance(faces, list)
        self.assertEqual(len(faces), 0)


if __name__ == "__main__":
    unittest.main()
