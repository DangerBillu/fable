import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from runtime.state.types import SensitiveCategory, ClassificationLevel, VisualFinding


class VisualClassifierTests(unittest.TestCase):
    """Tests for visual content classification."""

    def test_classifier_import(self):
        """VisualClassifier can be imported without crashing."""
        from runtime.privacy.visual_classifier import VisualClassifier
        classifier = VisualClassifier()
        self.assertIsNotNone(classifier)

    def test_classify_blank_image(self):
        """Classifier returns a list for a blank image."""
        from runtime.privacy.visual_classifier import VisualClassifier
        from PIL import Image
        import io

        img = Image.new("RGB", (200, 200), color=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        classifier = VisualClassifier()
        findings = classifier.classify(image_bytes)
        self.assertIsInstance(findings, list)

    def test_findings_are_visual_finding_objects(self):
        """Any findings returned should be VisualFinding objects."""
        from runtime.privacy.visual_classifier import VisualClassifier
        from PIL import Image
        import io

        img = Image.new("RGB", (200, 200), color=(0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        classifier = VisualClassifier()
        findings = classifier.classify(image_bytes)
        for finding in findings:
            self.assertIsInstance(finding, VisualFinding)

    def test_visual_finding_dataclass(self):
        """VisualFinding dataclass is frozen and has expected fields."""
        finding = VisualFinding(
            category=SensitiveCategory.QR_CODE,
            classification=ClassificationLevel.RESTRICTED,
            description="Detected QR code",
            confidence=0.9,
            bbox=(10, 20, 100, 100),
            source="opencv",
        )
        self.assertEqual(finding.category, SensitiveCategory.QR_CODE)
        self.assertEqual(finding.classification, ClassificationLevel.RESTRICTED)
        self.assertEqual(finding.bbox, (10, 20, 100, 100))
        with self.assertRaises(AttributeError):
            finding.confidence = 0.5  # frozen dataclass

    def test_classify_invalid_bytes(self):
        """Classifier should gracefully handle invalid image bytes."""
        from runtime.privacy.visual_classifier import VisualClassifier

        classifier = VisualClassifier()
        findings = classifier.classify(b"not_an_image")
        self.assertIsInstance(findings, list)


if __name__ == "__main__":
    unittest.main()
