import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class HuggingFaceClientTests(unittest.TestCase):
    """Tests for HuggingFace Inference API client."""

    def test_client_import(self):
        """HuggingFaceClient can be imported."""
        from agent.hf import HuggingFaceClient
        self.assertIsNotNone(HuggingFaceClient)

    def test_client_initialization(self):
        """HuggingFaceClient initializes with expected fields."""
        from agent.hf import HuggingFaceClient
        client = HuggingFaceClient(api_token="test-token-123")
        self.assertEqual(client.api_token, "test-token-123")

    def test_is_available_without_token(self):
        """Client reports unavailable when token is empty."""
        from agent.hf import HuggingFaceClient
        client = HuggingFaceClient(api_token="")
        self.assertFalse(client.is_available())

    def test_describe_image_returns_string(self):
        """describe_image should return a string (empty on failure)."""
        from agent.hf import HuggingFaceClient
        client = HuggingFaceClient(api_token="fake-token")
        # With a fake token, the API call will fail, but it should return empty string
        result = client.describe_image("base64imagedata")
        self.assertIsInstance(result, str)

    def test_generate_text_returns_string(self):
        """generate_text should return a string (empty on failure)."""
        from agent.hf import HuggingFaceClient
        client = HuggingFaceClient(api_token="fake-token")
        result = client.generate_text("Test prompt")
        self.assertIsInstance(result, str)

    def test_client_default_models(self):
        """Client uses expected default model names."""
        from agent.hf import HuggingFaceClient
        client = HuggingFaceClient(api_token="test")
        self.assertIn("blip2", client.vision_model.lower())
        self.assertIn("mistral", client.text_model.lower())


if __name__ == "__main__":
    unittest.main()
