import os
import re
import subprocess
from pypdf import PdfReader

def clean_latex_to_text(latex_code: str) -> str:
    """Strips common LaTeX commands to produce clean readable text for LLM scoring."""
    # Remove comments
    text = re.sub(r"%.*", "", latex_code)
    # Remove commands like \definecolor, \usepackage, etc.
    text = re.sub(r"\\(usepackage|definecolor|setlength|pagestyle|newcommand|newenvironment).*?(\n|$)", "", text)
    # Replace common formatting macros with text content
    text = re.sub(r"\\[a-zA-Z]+\*?\{([^}]*)\}", r"\1", text)
    # Replace remaining commands
    text = re.sub(r"\\[a-zA-Z]+", " ", text)
    # Clean up excess whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text content from a PDF file."""
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        print(f"[Warning] pypdf extraction failed ({e}), attempting pdftotext fallback...")
        text = ""

    if not text.strip():
        try:
            result = subprocess.run(
                ["pdftotext", pdf_path, "-"],
                capture_output=True,
                text=True,
                check=True
            )
            text = result.stdout
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF: {e}")

    return text.strip()

def load_cv_text(tex_path: str = None, pdf_path: str = None) -> tuple:
    """
    Loads CV text. Prioritizes main.tex if available, falling back to PDF.
    Returns tuple: (cv_text, cv_type)
    """
    if tex_path is None:
        tex_path = "templates/main.tex" if os.path.exists("templates/main.tex") else "main.tex"
    if pdf_path is None:
        pdf_path = "data/CV_Fahad.pdf" if os.path.exists("data/CV_Fahad.pdf") else "CV_Fahad.pdf"

    if os.path.exists(tex_path):
        with open(tex_path, "r", encoding="utf-8") as f:
            raw_tex = f.read()
        cv_text = clean_latex_to_text(raw_tex)
        return cv_text, f"LaTeX ({tex_path})"
    elif os.path.exists(pdf_path):
        cv_text = extract_text_from_pdf(pdf_path)
        return cv_text, f"PDF ({pdf_path})"
    else:
        raise FileNotFoundError(f"Neither '{tex_path}' nor '{pdf_path}' could be found.")
