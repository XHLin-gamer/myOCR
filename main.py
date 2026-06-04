import sys
import io
import os
import glob
import argparse

# Ensure stdout and stderr handle UTF-8 characters without crashing on Windows
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from services import (
    get_ocr_service,
    get_post_processor,
    GeminiTranslator,
    clean_and_format_layout,
    render_markdown_to_pdf,
)

def main():

    parser = argparse.ArgumentParser(description="Convert scanned images to Markdown and PDF using local/cloud OCR.")
    parser.add_argument("-i", "--input", help="Directory containing images (JPEG/PNG)")
    parser.add_argument("-o", "--output", help="Output Markdown file name")
    parser.add_argument("-p", "--provider", help="OCR Provider ('easyocr', 'gemini', 'ollama')")
    parser.add_argument("-r", "--refine", choices=["ollama", "gemini"], help="Enable layout refinement with 'ollama' or 'gemini'")
    parser.add_argument("--refine-model", help="LLM model name for refinement (default for ollama: qwen3.5:2b, for gemini: gemini-3.1-flash-lite)")
    parser.add_argument("-f", "--pdf", help="Output PDF file name (optional)")
    parser.add_argument("-t", "--translate", help="Target language for translation (optional, e.g. english, chinese)")
    args = parser.parse_args()

    print("========================================")
    print("      OCR to Markdown CLI Converter     ")
    print("========================================")

    # Resolve input directory
    image_dir = args.input
    if not image_dir:
        default_dir = os.path.join("data", "RA_manu")
        try:
            val = input(f"Enter input folder path [default: {default_dir}]: ").strip()
            image_dir = val if val else default_dir
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            return

    # Resolve output file
    output_file = args.output
    if not output_file:
        default_out = "output.md"
        try:
            val = input(f"Enter output Markdown file [default: {default_out}]: ").strip()
            output_file = val if val else default_out
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            return

    # Resolve provider
    provider = args.provider
    if not provider:
        default_provider = os.environ.get("OCR_PROVIDER", "easyocr").lower()
        try:
            val = input(f"Enter OCR Provider (easyocr/gemini/ollama) [default: {default_provider}]: ").strip().lower()
            provider = val if val else default_provider
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            return

    os.environ["OCR_PROVIDER"] = provider

    # Resolve refinement options
    refine_provider = args.refine
    refine_model = args.refine_model
    if not args.refine and not args.provider:
        # Prompt only if run interactively without args
        try:
            val = input("Enable layout refinement? (ollama/gemini/No) [default: No]: ").strip().lower()
            if val in ["ollama", "gemini"]:
                refine_provider = val
            elif val in ["y", "yes"]:
                refine_provider = "ollama"
            else:
                refine_provider = None

            if refine_provider:
                default_m = "gemini-3.1-flash-lite" if refine_provider == "gemini" else "qwen3.5:2b"
                m_val = input(f"Enter model name [default: {default_m}]: ").strip()
                refine_model = m_val if m_val else default_m
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            return

    # Set default model name if refine was enabled via CLI args but no model was specified
    if refine_provider and not refine_model:
        refine_model = "gemini-3.1-flash-lite" if refine_provider == "gemini" else "qwen3.5:2b"

    # Resolve PDF option
    pdf_file = args.pdf
    if not args.pdf and not args.provider:
        # Prompt only if run interactively without args
        try:
            val = input("Convert generated Markdown to PDF? (Y/n): ").strip().lower()
            if val in ["", "y", "yes"]:
                pdf_file = output_file.rsplit(".", 1)[0] + ".pdf"
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            return

    # Resolve translation option
    translate_lang = args.translate
    if not args.translate and not args.provider:
        # Prompt only if run interactively without args
        try:
            val = input("Translate output to another language? (e.g., english, chinese, or Enter to skip): ").strip()
            if val:
                translate_lang = val
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled.")
            return

    print("-" * 40)
    print(f"Selected Provider: {provider.upper()}")
    print(f"Input Directory:   {image_dir}")
    print(f"Output File:       {output_file}")
    if refine_provider:
        print(f"Refinement:        ENABLED (provider: {refine_provider.upper()}, model: {refine_model})")
    else:
        print("Refinement:        DISABLED")
    if translate_lang:
        print(f"Translation:       ENABLED (target language: {translate_lang})")
    else:
        print("Translation:       DISABLED")
    if pdf_file:
        print(f"PDF Output:        {pdf_file}")
    else:
        print("PDF Output:        DISABLED")
    print("-" * 40)

    if (provider == "gemini" or refine_provider == "gemini") and not os.environ.get("GEMINI_API_KEY"):
        print("Warning: GEMINI_API_KEY environment variable is not set. Gemini API calls will fail.")

    if not os.path.exists(image_dir):
        print(f"Error: Directory '{image_dir}' does not exist.")
        return

    # Find all jpg, jpeg, png, JPG, JPEG, PNG images
    image_extensions = ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]
    raw_paths = []
    for ext in image_extensions:
        raw_paths.extend(glob.glob(os.path.join(image_dir, ext)))
    
    # Ensure unique paths (Windows glob is case-insensitive, which matches both lowercase and uppercase extensions)
    unique_paths = {}
    for p in raw_paths:
        unique_paths[os.path.abspath(p).lower()] = p
    image_paths = sorted(unique_paths.values())
    
    if not image_paths:
        print(f"Error: No images found in directory '{image_dir}'.")
        return
        
    print(f"Found {len(image_paths)} images to convert.")
    
    # Initialize OCR Service via factory
    try:
        ocr_service = get_ocr_service()
    except Exception as e:
        print(f"Failed to initialize OCR service: {e}")
        return

    # Initialize layout post-processor if enabled
    post_processor = None
    if refine_provider:
        print(f"Initializing layout post-processor '{refine_provider}'...")
        try:
            post_processor = get_post_processor(provider=refine_provider, model_name=refine_model)
        except Exception as e:
            print(f"Failed to initialize post-processor: {e}")
            return

    # Initialize translator if enabled
    translator = None
    if translate_lang:
        print(f"Initializing Gemini translator for target language '{translate_lang}'...")
        try:
            translator = GeminiTranslator(target_lang=translate_lang)
        except Exception as e:
            print(f"Failed to initialize translator: {e}")
            return

    # Phase 1: OCR & Layout Refinement for all pages
    pages_data = []
    print("\n=== PHASE 1: OCR & Layout Refinement ===")
    for idx, path in enumerate(image_paths):
        filename = os.path.basename(path)
        print(f"[{idx + 1}/{len(image_paths)}] Processing {filename}...")
        try:
            page_md = ocr_service.image_to_markdown(path)
            
            if post_processor:
                print(f"   Refining layout with '{refine_provider}' ({refine_model})...")
                page_md = post_processor.process_text(page_md)
                
            page_md = clean_and_format_layout(page_md)
            pages_data.append((filename, page_md))
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    # Phase 2: Translation for all pages (if enabled)
    translated_pages = []
    if translator:
        print("\n=== PHASE 2: Document Translation ===")
        for idx, (filename, page_md) in enumerate(pages_data):
            print(f"[{idx + 1}/{len(pages_data)}] Translating page {filename} to '{translate_lang}'...")
            try:
                translated_md = translator.translate_text(page_md)
                translated_pages.append((filename, translated_md))
            except Exception as e:
                print(f"Error translating page {filename}: {e}")
                translated_pages.append((filename, page_md))
    else:
        translated_pages = pages_data

    # Phase 3: Translation Review & Layout Alignment
    full_markdown_parts = []
    if translator:
        print("\n=== PHASE 3: Translation Review & Layout Alignment ===")
        reviewed_pages = translator.review_translation(translated_pages, log_func=print)
        for filename, page_md in reviewed_pages:
            # Deterministic layout cleaning
            page_md = clean_and_format_layout(page_md)
            page_section = f"<!-- START PAGE: {filename} -->\n{page_md}\n<!-- END PAGE: {filename} -->"
            full_markdown_parts.append(page_section)
    else:
        for filename, page_md in translated_pages:
            page_section = f"<!-- START PAGE: {filename} -->\n{page_md}\n<!-- END PAGE: {filename} -->"
            full_markdown_parts.append(page_section)

    full_markdown = "\n\n---\n\n".join(full_markdown_parts)
    
    print(f"\nWriting complete markdown to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(full_markdown)
        
    print("OCR to Markdown conversion finished successfully!")

    # Render PDF if requested
    if pdf_file:
        print(f"\nGenerating styled PDF: {pdf_file}...")
        try:
            render_markdown_to_pdf(full_markdown, pdf_file)
            print(f"PDF generated successfully at: {pdf_file}")
        except Exception as e:
            print(f"Error generating PDF: {e}")

if __name__ == "__main__":
    main()
