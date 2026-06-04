import os
import requests

class GeminiTranslator:
    """
    Translation plugin using Google Gemini 3.1 Flash-Lite API.
    Translates Markdown text to a specified target language while preserving Markdown syntax and structure.
    """
    def __init__(self, target_lang: str, model_name: str = "gemini-3.1-flash-lite"):
        self.target_lang = target_lang
        self.model_name = model_name
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it in your .env file or environment.")

    def translate_text(self, text: str) -> str:
        if not text or not text.strip():
            return text

        prompt = (
            f"You are a professional translator. Translate the following Japanese document into {self.target_lang}.\n"
            "Rules:\n"
            "1. Strictly preserve all Markdown elements, headings (e.g., ##, ###), lists, numbers, bold text, and HTML comments exactly as they are.\n"
            "2. Translate only the actual text content.\n"
            "3. Keep proper names, abbreviation names, and specific acronyms in their original form if appropriate.\n"
            "4. Output ONLY the translated Markdown. Do not wrap the output in markdown code blocks like ```markdown.\n\n"
            f"Document:\n{text}"
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
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            result = response.json()
            translated = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            return translated if translated else text
        except Exception as e:
            print(f"Warning: Gemini translation to {self.target_lang} failed: {e}")
            return text

    def review_translation(self, pages_data: list, log_func=print) -> list:
        """
        Final review stage:
        1. Compiles a global glossary of terms from all translated pages.
        2. Reviews each translated page page-by-page using the glossary to ensure uniform word choice and layout.
        """
        if not pages_data:
            return pages_data

        # 1. Compile full text for glossary extraction
        full_text = "\n\n---\n\n".join(text for _, text in pages_data)
        
        log_func("Extracting global terminology for review...")
        prompt = (
            "Analyze the following translated document. Identify key recurring roles, organizations, "
            "fees, or policies, and define the standard uniform English translations to use. "
            "Output ONLY a raw JSON dictionary mapping terms/concepts to their uniform English translation. "
            "Do not include any other text or markdown formatting blocks. "
            "Example format: {\"Resident Assistant\": \"Resident Assistant (RA)\", \"謝金\": \"Honorarium\"}\n\n"
            f"Document:\n{full_text}"
        )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "thinkingConfig": {
                    "thinkingBudget": 0
                }
            }
        }

        glossary = "{}"
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            response.raise_for_status()
            result = response.json()
            glossary = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            log_func(f"Global glossary extracted: {glossary}")
        except Exception as e:
            log_func(f"Warning: Terminology extraction failed: {e}. Proceeding with default review.")

        # 2. Review page-by-page
        reviewed_pages = []
        for idx, (filename, page_md) in enumerate(pages_data):
            log_func(f"[{idx + 1}/{len(pages_data)}] Reviewing and aligning translation for {filename}...")
            
            review_prompt = (
                f"Review the following translated Markdown page to ensure uniform word choice and proper layout alignment.\n"
                f"Refer to this global glossary of standardized translations for consistency:\n{glossary}\n\n"
                "Rules:\n"
                "1. Correct any terminology discrepancies to align with the global glossary.\n"
                "2. Keep the translation natural and check for any awkward phrasing or grammar.\n"
                "3. Ensure the section headings (##, ###) and paragraph spacing are clean and properly aligned.\n"
                "4. Output ONLY the reviewed Markdown. Do not wrap in markdown code blocks.\n\n"
                f"Page Content:\n{page_md}"
            )
            
            page_payload = {
                "contents": [{
                    "parts": [{"text": review_prompt}]
                }],
                "generationConfig": {
                    "thinkingConfig": {
                        "thinkingBudget": 0
                    }
                }
            }
            
            try:
                response = requests.post(url, headers=headers, json=page_payload, timeout=90)
                response.raise_for_status()
                result = response.json()
                reviewed_text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                if reviewed_text:
                    reviewed_pages.append((filename, reviewed_text))
                else:
                    reviewed_pages.append((filename, page_md))
            except Exception as e:
                log_func(f"Warning: Review failed for {filename}: {e}. Retaining original translation.")
                reviewed_pages.append((filename, page_md))

        return reviewed_pages

