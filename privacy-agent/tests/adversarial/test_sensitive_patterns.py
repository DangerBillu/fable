import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from runtime.privacy import PrivacyDetector
from runtime.tokenization import TokenVault


class SensitivePatternTests(unittest.TestCase):
    def test_phase_one_patterns_have_no_known_false_negatives(self):
        detector = PrivacyDetector(TokenVault())
        cases = [
            "john@example.com",
            "+91 9876543210",
            "4111 1111 1111 1111",
            "sk-example-test-key",
            "Bearer abcdefghijklmnop",
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature",
            "-----BEGIN PRIVATE KEY-----",
            "123-45-6789",
        ]
        for case in cases:
            with self.subTest(case=case):
                sanitized, findings = detector.inspect_text(case)
                self.assertTrue(findings)
                self.assertNotIn(case, sanitized)


if __name__ == "__main__":
    unittest.main()

