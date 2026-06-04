import os
import base64
import requests
from .base import BaseOCRService

class GeminiOCRService(BaseOCRService):
    """
    Cloud OCR Service using Google Gemini 3.1 Flash-Lite API.
    Sends raw image bytes and prompts the model to return high-fidelity Markdown.
    """
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it in your .env file or environment.")

    def image_to_markdown(self, image_path: str) -> str:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        mime_type = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        
        prompt = (
            "Transcribe the text in this image into highly accurate Markdown format. "
            "Do not translate the text; keep it in its original Japanese language.\n"
            "Formatting Rules:\n"
            "1. Format section headers using proper Markdown headings:\n"
            "   - Convert Roman numeral sections (e.g., Ⅰ. はじめに, Ⅱ. レジデント・アシスタント...) into H2 headings (e.g., `## Ⅰ. はじめに`).\n"
            "   - Convert major sub-sections starting with numbers (e.g., 1. RAの資格, 2. RAの活動...) into H3 headings (e.g., `### 1. RAの資格`).\n"
            "2. Strip out original page numbers (e.g., lines containing just '- 1 -', '• 1 -', or solo numbers like '6' at the bottom of the page).\n"
            "3. Strictly preserve all other document structures, lists, and tables.\n"
            "Output ONLY the raw markdown transcription. Do not wrap the output in markdown code blocks like ```markdown."
        )


        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": image_data
                        }
                    }
                ]
            }],
            "generationConfig": {
                "thinkingConfig": {
                    "thinkingBudget": 0
                }
            }
        }

        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()

        try:
            return result["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError):
            raise RuntimeError(f"Unexpected response structure from Gemini API: {result}")
