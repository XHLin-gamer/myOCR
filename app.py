import os
import sys
import io

# Ensure stdout and stderr handle UTF-8 characters without crashing on Windows
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import glob
import threading
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from services import (
    get_ocr_service,
    get_post_processor,
    GeminiTranslator,
    clean_and_format_layout,
    render_markdown_to_pdf,
    update_env_file,
)

app = FastAPI(title="myOCR Web UI")

# Ensure static directory exists
os.makedirs("static", exist_ok=True)

# Mount static files (will serve index.html)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Global conversion progress state
progress_state = {
    "status": "idle",  # idle, running, completed, error
    "current_step": 0,
    "total_steps": 0,
    "current_file": "",
    "logs": [],
    "output_md": "",
    "output_pdf": "",
    "error_message": ""
}

class ConvertRequest(BaseModel):
    input_dir: str
    output_md: str
    provider: str
    refine: str  # "none", "gemini", "ollama"
    refine_model: str
    translate: str  # "none" or target language name
    pdf: bool

def run_conversion_in_background(req: ConvertRequest):
    global progress_state
    progress_state["status"] = "running"
    progress_state["logs"] = []
    progress_state["current_step"] = 0
    progress_state["total_steps"] = 0
    progress_state["current_file"] = ""
    progress_state["error_message"] = ""
    progress_state["output_md"] = ""
    progress_state["output_pdf"] = ""

    def log(msg):
        progress_state["logs"].append(msg)
        print(f"[WebUI] {msg}")

    try:
        # Search for images
        image_extensions = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
        raw_paths = []
        for ext in image_extensions:
            raw_paths.extend(glob.glob(os.path.join(req.input_dir, ext)))
        
        unique_paths = {}
        for p in raw_paths:
            unique_paths[os.path.abspath(p).lower()] = p
        image_paths = sorted(unique_paths.values())

        if not image_paths:
            raise ValueError(f"No images found in directory '{req.input_dir}'.")

        total_pages = len(image_paths)
        if req.translate and req.translate != "none":
            progress_state["total_steps"] = total_pages * 3
        else:
            progress_state["total_steps"] = total_pages

        log(f"Found {total_pages} images to process.")

        # Set environment variables for the factory
        os.environ["OCR_PROVIDER"] = req.provider

        log(f"Initializing OCR Service '{req.provider.upper()}'...")
        ocr_service = get_ocr_service()

        post_processor = None
        if req.refine and req.refine != "none":
            model = req.refine_model
            if not model:
                model = "gemini-3.1-flash-lite" if req.refine == "gemini" else "qwen3.5:2b"
            log(f"Initializing layout post-processor '{req.refine.upper()}' (model: {model})...")
            post_processor = get_post_processor(provider=req.refine, model_name=model)

        translator = None
        if req.translate and req.translate != "none":
            log(f"Initializing translation plugin (target language: {req.translate})...")
            translator = GeminiTranslator(target_lang=req.translate)

        # Phase 1: OCR & Layout Refinement for all pages
        pages_data = []
        log("=== PHASE 1: OCR & Layout Refinement ===")
        for idx, path in enumerate(image_paths):
            filename = os.path.basename(path)
            progress_state["current_step"] = idx + 1
            progress_state["current_file"] = f"OCR: {filename}"
            log(f"[{idx + 1}/{total_pages}] OCR & Layout Processing for {filename}...")

            # 1. OCR Transcribe
            page_md = ocr_service.image_to_markdown(path)

            # 2. Refine Layout
            if post_processor:
                log(f"   Refining layout with '{req.refine}'...")
                page_md = post_processor.process_text(page_md)

            # 3. Deterministic formatting & page number stripping
            page_md = clean_and_format_layout(page_md)
            
            pages_data.append((filename, page_md))

        # Phase 2: Translation for all pages (if enabled)
        translated_pages = []
        if translator:
            log("=== PHASE 2: Document Translation ===")
            for idx, (filename, page_md) in enumerate(pages_data):
                progress_state["current_step"] = total_pages + idx + 1
                progress_state["current_file"] = f"Translate: {filename}"
                log(f"[{idx + 1}/{total_pages}] Translating page {filename} to '{req.translate}'...")

                translated_md = translator.translate_text(page_md)
                translated_pages.append((filename, translated_md))
        else:
            translated_pages = pages_data

        # Phase 3: Translation Review & Layout Alignment
        full_markdown_parts = []
        if translator:
            log("=== PHASE 3: Translation Review & Layout Alignment ===")
            
            step_container = {"idx": 0}
            def review_log(msg):
                log(msg)
                if "Reviewing and aligning" in msg:
                    step_container["idx"] += 1
                    progress_state["current_step"] = (total_pages * 2) + step_container["idx"]
                    try:
                        filename = msg.split("translation for ")[1].split("...")[0]
                        progress_state["current_file"] = f"Review: {filename}"
                    except Exception:
                        pass

            reviewed_pages = translator.review_translation(translated_pages, log_func=review_log)
            for filename, page_md in reviewed_pages:
                page_md = clean_and_format_layout(page_md)
                page_section = f"<!-- START PAGE: {filename} -->\n{page_md}\n<!-- END PAGE: {filename} -->"
                full_markdown_parts.append(page_section)
        else:
            for filename, page_md in translated_pages:
                page_section = f"<!-- START PAGE: {filename} -->\n{page_md}\n<!-- END PAGE: {filename} -->"
                full_markdown_parts.append(page_section)

        full_markdown = "\n\n---\n\n".join(full_markdown_parts)

        # Write markdown
        log(f"Saving Markdown output to '{req.output_md}'...")
        with open(req.output_md, "w", encoding="utf-8") as f:
            f.write(full_markdown)
        progress_state["output_md"] = req.output_md

        # Generate PDF if requested
        if req.pdf:
            pdf_path = req.output_md.rsplit(".", 1)[0] + ".pdf"
            log(f"Generating styled PDF to '{pdf_path}'...")
            try:
                render_markdown_to_pdf(full_markdown, pdf_path)
                progress_state["output_pdf"] = pdf_path
                log("PDF output generated successfully!")
            except Exception as e:
                log(f"Warning: PDF generation failed: {e}")

        log("All tasks completed successfully!")
        progress_state["status"] = "completed"

    except Exception as e:
        log(f"Error occurred during execution: {e}")
        progress_state["status"] = "error"
        progress_state["error_message"] = str(e)

@app.post("/api/convert")
def start_conversion(req: ConvertRequest, background_tasks: BackgroundTasks):
    global progress_state
    if progress_state["status"] == "running":
        return {"error": "A conversion process is already running."}
    
    background_tasks.add_task(run_conversion_in_background, req)
    return {"status": "started"}

@app.get("/api/progress")
def get_progress():
    return progress_state

@app.get("/api/download")
def download_file(path: str):
    if not os.path.exists(path):
        return {"error": "File not found"}
    return FileResponse(path, filename=os.path.basename(path))

class SettingsRequest(BaseModel):
    gemini_api_key: str

@app.get("/api/settings")
def get_settings():
    key = os.environ.get("GEMINI_API_KEY", "")
    masked_key = ""
    if key:
        if len(key) > 8:
            masked_key = key[:4] + "..." + key[-4:]
        else:
            masked_key = "********"
    
    return {
        "gemini_api_key": masked_key,
        "gemini_api_key_set": bool(key),
    }

@app.post("/api/settings")
def save_settings(req: SettingsRequest):
    key = req.gemini_api_key.strip()
    if not key:
        return {"error": "API Key cannot be empty."}
    
    if "..." in key or "*" in key:
        return {"status": "success", "message": "API key was not modified."}
    
    os.environ["GEMINI_API_KEY"] = key
    try:
        update_env_file("GEMINI_API_KEY", key)
        return {"status": "success", "message": "Settings saved to .env"}
    except Exception as e:
        return {"error": f"Failed to save settings: {e}"}

@app.get("/")
def read_root():
    return FileResponse("static/index.html")
