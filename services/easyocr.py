import os
import re
import statistics
from typing import List, Any
from .base import BaseOCRService

class EasyOCRService(BaseOCRService):
    """
    Local OCR Service using EasyOCR.
    Loads PyTorch and EasyOCR dynamically to prevent dependency errors when using cloud APIs.
    """
    def __init__(self):
        try:
            import torch
            import easyocr
            self.torch = torch
            self.easyocr = easyocr
        except ImportError:
            raise ImportError(
                "EasyOCR and PyTorch are required for local OCR. "
                "Please install them or use a cloud API provider (e.g. Gemini)."
            )
            
        self.use_gpu = self.torch.cuda.is_available()
        print(f"Initializing EasyOCR (GPU={self.use_gpu})...")
        self.reader = self.easyocr.Reader(['ja', 'en'], gpu=self.use_gpu)

    def image_to_markdown(self, image_path: str) -> str:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at {image_path}")

        results = self.reader.readtext(image_path, detail=1)
        return self._reconstruct_layout(results)

    def _reconstruct_layout(self, results: List[Any]) -> str:
        if not results:
            return ""

        blocks = []
        for bbox, text, conf in results:
            if not text or not text.strip():
                continue
            
            cleaned_text = text.strip(" ~`'\"‥…・。_,-;:;")
            if not cleaned_text:
                continue

            if conf < 0.1:
                continue

            meaningful_pattern = re.compile(
                r'[a-zA-Z0-9\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff①-⑳Ⅰ-Ⅻ]'
            )
            if not meaningful_pattern.search(cleaned_text):
                continue

            if len(cleaned_text) == 1:
                if re.match(r'[0-9①-⑳]', cleaned_text):
                    if conf < 0.2:
                        continue
                else:
                    if conf < 0.35:
                        continue

            xs = [p[0] for p in bbox]
            ys = [p[1] for p in bbox]
            top = min(ys)
            bottom = max(ys)
            left = min(xs)
            right = max(xs)
            height = bottom - top
            center_y = (top + bottom) / 2.0

            blocks.append({
                'text': cleaned_text,
                'left': left,
                'right': right,
                'height': height,
                'center_y': center_y
            })

        if not blocks:
            return ""

        heights = [b['height'] for b in blocks]
        median_height = statistics.median(heights)
        blocks.sort(key=lambda b: b['center_y'])

        lines = []
        for b in blocks:
            placed = False
            for line in lines:
                avg_center_y = sum(item['center_y'] for item in line) / len(line)
                avg_height = sum(item['height'] for item in line) / len(line)

                if abs(b['center_y'] - avg_center_y) < avg_height * 0.5:
                    line.append(b)
                    placed = True
                    break
            if not placed:
                lines.append([b])

        lines.sort(key=lambda line: sum(item['center_y'] for item in line) / len(line))

        reconstructed_lines = []
        for line in lines:
            line.sort(key=lambda item: item['left'])
            max_height = max(item['height'] for item in line)
            
            line_text = ""
            for i, item in enumerate(line):
                if i > 0:
                    prev_item = line[i-1]
                    gap = item['left'] - prev_item['right']
                    avg_h = (item['height'] + prev_item['height']) / 2.0
                    if gap > avg_h * 1.2:
                        line_text += "   "
                    elif gap > avg_h * 0.5:
                        line_text += " "
                line_text += item['text']

            line_text = self._clean_japanese_spaces(line_text.strip())
            is_large_text = max_height > (median_height * 1.5)
            reconstructed_lines.append((line_text, is_large_text))

        markdown_parts = []
        roman_pattern = re.compile(r'^([IVXLCDM]+\.|[Ⅰ-Ⅻ]\.?)\s*(.*)')
        section_pattern = re.compile(r'^(\d+\.)\s*(.*)')
        paren_pattern = re.compile(r'^(\(\d+\))\s*(.*)')
        circled_pattern = re.compile(r'^([①-⑳])\s*(.*)')

        for line_text, is_large_text in reconstructed_lines:
            if not line_text:
                continue

            m_roman = roman_pattern.match(line_text)
            m_sec = section_pattern.match(line_text)
            m_paren = paren_pattern.match(line_text)
            m_circle = circled_pattern.match(line_text)

            if m_roman:
                markdown_parts.append(f"## {m_roman.group(1)} {m_roman.group(2)}")
            elif m_sec:
                markdown_parts.append(f"### {m_sec.group(1)} {m_sec.group(2)}")
            elif m_paren:
                markdown_parts.append(f"#### {m_paren.group(1)} {m_paren.group(2)}")
            elif m_circle:
                markdown_parts.append(f"##### {m_circle.group(1)} {m_circle.group(2)}")
            elif is_large_text and len(line_text) < 40:
                markdown_parts.append(f"# {line_text}")
            else:
                markdown_parts.append(line_text)

        return "\n\n".join(markdown_parts)

    def _clean_japanese_spaces(self, text: str) -> str:
        text = re.sub(
            r'(?<=[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff])\s+(?=[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff])', 
            '', 
            text
        )
        text = re.sub(
            r'(?<=[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff])\s+(?=[a-zA-Z0-9])', 
            '', 
            text
        )
        text = re.sub(
            r'(?<=[a-zA-Z0-9])\s+(?=[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff])', 
            '', 
            text
        )
        return text
