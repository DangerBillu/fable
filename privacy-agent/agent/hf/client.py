import json
import urllib.request
from dataclasses import dataclass

@dataclass
class HuggingFaceClient:
    api_token: str
    vision_model: str = "Salesforce/blip2-opt-2.7b"
    text_model: str = "mistralai/Mistral-7B-Instruct-v0.3"

    def describe_image(self, image_b64: str) -> str:
        try:
            url = f"https://api-inference.huggingface.co/models/{self.vision_model}"
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            payload = {"inputs": image_b64}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                return data[0]["generated_text"]
            return str(data)
        except Exception:
            return ""

    def generate_text(self, prompt: str) -> str:
        try:
            url = f"https://api-inference.huggingface.co/models/{self.text_model}"
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            payload = {"inputs": prompt, "parameters": {"max_new_tokens": 512}}
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                return data[0]["generated_text"]
            return str(data)
        except Exception:
            return ""

    def is_available(self) -> bool:
        if not self.api_token:
            return False
        try:
            url = f"https://api-inference.huggingface.co/models/{self.text_model}"
            headers = {"Authorization": f"Bearer {self.api_token}"}
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception:
            return False
