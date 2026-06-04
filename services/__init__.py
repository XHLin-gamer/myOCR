import os
from .base import BaseOCRService
from .easyocr import EasyOCRService
from .gemini import GeminiOCRService
from .ollama import OllamaGLMOCRService
from .post_processor import get_post_processor
from .translator import GeminiTranslator
from .utils import (
    clean_and_format_layout,
    update_env_file,
)
from .pdf import render_markdown_to_pdf


# Automatically load environment variables from .env if present
def _load_dotenv(path=".env"):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

_load_dotenv()

def get_ocr_service(provider_name: str = None) -> BaseOCRService:
    """
    Factory function to retrieve the configured OCR service provider.
    Resolves from environment variable OCR_PROVIDER: 'easyocr', 'gemini', or 'ollama'.
    """
    if provider_name is None:
        provider_name = os.environ.get("OCR_PROVIDER", "easyocr").lower()

    if provider_name == "gemini":
        return GeminiOCRService()
    elif provider_name in ["ollama", "glm-ocr"]:
        return OllamaGLMOCRService()
    else:
        return EasyOCRService()
