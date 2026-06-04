from markdown_pdf import MarkdownPdf, Section

def render_markdown_to_pdf(markdown_text: str, pdf_path: str) -> None:
    """
    Render a Markdown string to a styled PDF using A4 layout and custom CSS styling.
    """
    css = """
    @page {
        size: A4;
        margin: 25mm 20mm;
    }
    body {
        font-family: "Yu Gothic", "Meiryo", "MS Gothic", sans-serif;
        color: #2d3748;
        line-height: 1.8;
        font-size: 11pt;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #1a202c;
        font-weight: bold;
        margin-top: 1.5em;
        margin-bottom: 0.6em;
    }
    h1 {
        font-size: 22pt;
        border-bottom: 3px solid #3182ce;
        padding-bottom: 8px;
        text-align: center;
        margin-top: 1.5em;
        margin-bottom: 1.2em;
        break-after: avoid;
    }
    h2 {
        font-size: 16pt;
        border-bottom: 1.5px solid #4299e1;
        padding-bottom: 5px;
        margin-top: 1.8em;
        break-after: avoid;
    }
    h3 {
        font-size: 13pt;
        margin-top: 1.5em;
        break-after: avoid;
    }
    p {
        margin-top: 0;
        margin-bottom: 1.2em;
        text-align: justify;
    }
    ul, ol {
        margin-top: 0;
        margin-bottom: 1.2em;
        padding-left: 24px;
    }
    li {
        margin-bottom: 0.4em;
    }
    hr {
        break-before: page;
        border: none;
        height: 0;
        margin: 0;
        padding: 0;
    }
    """
    pdf = MarkdownPdf(toc_level=2, optimize=True)
    pdf.add_section(Section(markdown_text, toc=False), user_css=css)
    pdf.save(pdf_path)
