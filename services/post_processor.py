import os
import requests

class BasePostProcessor:
    def process_text(self, text: str) -> str:
        raise NotImplementedError()


class OllamaPostProcessor(BasePostProcessor):
    """
    Post-processor using a local Ollama model (e.g. qwen3.5:2b, gemma3:1b, etc.)
    to merge unnaturally split lines and correct obvious OCR spelling errors.
    """
    def __init__(self, model_name: str = "qwen3.5:2b", host: str = "http://localhost:11434"):
        self.model_name = model_name
        self.host = host

    def process_text(self, text: str) -> str:
        if not text or not text.strip():
            return text

        # Check if the Ollama service is reachable
        try:
            requests.get(self.host, timeout=2)
        except requests.exceptions.RequestException:
            print(f"Warning: Could not connect to Ollama at {self.host}. Skipping LLM refinement.")
            return text

        prompt = (
            "あなたは日本語のOCRテキスト修正アシスタントです。不自然な改行（行の分割）を結合して読みやすい段落にし、"
            "明らかな誤字（例：「誓備員」→「警備員」、「先糞」→「先輩」、「タクシ一」→「タクシー」、「希院」→「病院」）のみを修正してください。\n"
            "追加のフォーマット指示：\n"
            "1. ページ番号（例：「- 1 -」や「• 1 -」のような単なる数字や記号のみの行、またはページの最下部にある単なる数字の行）は完全に削除してください。\n"
            "2. 見出しの階層構造（ローマ数字の「Ⅰ.」「Ⅱ.」「Ⅲ.」などや、「1.」「2.」「3.」で始まる大見出し）は、Markdownの見出し記号（例：章見出しは `## Ⅰ. はじめに`、節見出しは `### 1. RAの資格` など）に適切に変換してください。既に `#` や `##` がある場合はその構造を維持し、サイズが不自然な箇所を調整してください。\n"
            "文章の翻訳や要約、意味の変更は行わないでください。修正後の日本語テキストのみを出力してください。\n\n"
            f"テキスト：\n{text}"
        )

        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False
        }

        try:
            response = requests.post(url, json=payload, timeout=90)
            response.raise_for_status()
            corrected = response.json().get("response", "").strip()
            return corrected if corrected else text
        except Exception as e:
            print(f"Warning: Local Ollama post-processing failed: {e}")
            return text


class GeminiPostProcessor(BasePostProcessor):
    """
    Post-processor using cloud Gemini API (e.g. gemini-3.1-flash-lite)
    to merge unnaturally split lines and correct obvious OCR spelling errors.
    """
    def __init__(self, model_name: str = "gemini-3.1-flash-lite"):
        self.model_name = model_name
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it in your .env file or environment.")

    def process_text(self, text: str) -> str:
        if not text or not text.strip():
            return text

        prompt = (
            "あなたは日本語のOCRテキスト修正アシスタントです。不自然な改行（行の分割）を結合して読みやすい段落にし、"
            "明らかな誤字（例：「誓備員」→「警備員」、「先糞」→「先輩」、「タクシ一」→「タクシー」、「希院」→「病院」）のみを修正してください。\n"
            "追加のフォーマット指示：\n"
            "1. ページ番号（例：「- 1 -」や「• 1 -」のような単なる数字や記号のみの行、またはページの最下部にある単なる数字の行）は完全に削除してください。\n"
            "2. 見出しの階層構造（ローマ数字の「Ⅰ.」「Ⅱ.」「Ⅲ.」などや、「1.」「2.」「3.」で始まる大見出し）は、Markdownの見出し記号（例：章見出しは `## Ⅰ. はじめに`、節見出しは `### 1. RAの資格` など）に適切に変換してください。既に `#` や `##` がある場合はその構造を維持し、サイズが不自然な箇所を調整してください。\n"
            "文章の翻訳や要約、意味の変更は行わないでください。修正後の日本語テキストのみを出力してください。\n\n"
            f"テキスト：\n{text}"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "thinkingConfig": {
                    "thinkingBudget": 0
                }
            }
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            corrected = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            return corrected if corrected else text
        except Exception as e:
            print(f"Warning: Gemini API post-processing failed: {e}")
            return text


def get_post_processor(provider: str, model_name: str = None) -> BasePostProcessor:
    """
    Factory function to retrieve the configured Post-Processor provider.
    Resolves between 'ollama' and 'gemini'.
    """
    provider = provider.lower()
    if provider == "gemini":
        model = model_name or "gemini-3.1-flash-lite"
        return GeminiPostProcessor(model_name=model)
    else:
        model = model_name or "qwen3.5:2b"
        return OllamaPostProcessor(model_name=model)
