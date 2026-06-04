# myOCR

向vibe coding狠狠低头了。半个小时就能搓出来一个甚至挺好用的OCR。。。

![](./data/iconimage.jpg)
## Setup

Pls, guarantee the [uv](https://docs.astral.sh/uv/getting-started/) is installed

1. Install dependencies:
   ```bash
   uv sync
   ```
2. Configure your Gemini API Key in `.env`:
   ```env
   GEMINI_API_KEY=your_key_here
   ```

## Usage

- **CLI**: `python main.py`
- **Web UI**: `uv run uvicorn app:app --port 8000`
