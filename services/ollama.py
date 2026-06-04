import base64
import requests
from .base import BaseOCRService

class OllamaGLMOCRService(BaseOCRService):
    """
    Local/Remote OCR Service using local Ollama model `glm-ocr`.
    Communicates via Ollama generate endpoint.
    """
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host

    def image_to_markdown(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        url = f"{self.host}/api/generate"
        payload = {
            "model": "glm-ocr",
            "prompt": "Text Recognition:",
            "images": [image_data],
            "stream": False
        }

        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Could not connect to Ollama at {self.host}. Please run `ollama serve` and pull the `glm-ocr` model."
            )
