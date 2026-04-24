"""
Extract text, tables, and metadata from PDF files.

Strategy per page:
  1. pdfplumber  — fast, exact text for digital PDFs
  2. pytesseract — OCR fallback for scanned / image-only pages
     (requires Tesseract + Poppler installed on the system)
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Pages with fewer extracted characters than this are treated as image pages
# and sent through OCR.
_MIN_TEXT_CHARS = 30


# ─── OCR helpers ─────────────────────────────────────────────────────────────

def _ocr_available() -> bool:
    try:
        import pytesseract  # noqa: F401
        from pdf2image import convert_from_path  # noqa: F401
        return True
    except ImportError:
        return False


def _ocr_page(pdf_path: str, page_num: int) -> str:
    """Convert one PDF page to an image and return its OCR text."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        print(
            "\n[OCR] Missing libraries. Install them:\n"
            "  pip install pdf2image pytesseract Pillow\n"
            "  Windows — Poppler:   https://github.com/oschwartz10612/poppler-windows/releases\n"
            "  Windows — Tesseract: https://github.com/UB-Mannheim/tesseract/wiki",
            file=sys.stderr,
        )
        return ""

    try:
        print(f"  [OCR] page {page_num} … ", end="", flush=True)
        images = convert_from_path(
            pdf_path,
            first_page=page_num,
            last_page=page_num,
            dpi=200,
        )
        if images:
            text = pytesseract.image_to_string(images[0])
            print("done")
            return text
    except Exception as exc:
        print(f"failed ({exc})", file=sys.stderr)

    return ""


# ─── Main extractor ───────────────────────────────────────────────────────────

def extract_pdf(pdf_path: str, force_ocr: bool = False) -> dict:
    """
    Extract a PDF into a structured dict.

    Parameters
    ----------
    pdf_path  : path to the PDF file
    force_ocr : treat every page as an image (useful for fully scanned PDFs)

    Returns
    -------
    dict with keys: metadata, content (list of pages), full_text
    """
    try:
        import pdfplumber
    except ImportError:
        print("Error: pdfplumber not installed. Run: pip install pdfplumber", file=sys.stderr)
        sys.exit(1)

    path = Path(pdf_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if force_ocr and not _ocr_available():
        print("[Warning] --ocr flag set but OCR libraries not installed. Continuing without OCR.")
        force_ocr = False

    result: dict = {
        "metadata": {
            "filename":     path.name,
            "filepath":     str(path),
            "extracted_at": datetime.now().isoformat(),
            "pages":        0,
            "method":       "text",   # text | ocr | mixed
            "title":        "",
            "author":       "",
            "subject":      "",
            "creator":      "",
        },
        "content":   [],
        "full_text": "",
    }

    ocr_page_nums: list[int] = []

    with pdfplumber.open(str(path)) as pdf:
        result["metadata"]["pages"] = len(pdf.pages)

        if pdf.metadata:
            m = pdf.metadata
            result["metadata"]["title"]   = m.get("Title",   "") or ""
            result["metadata"]["author"]  = m.get("Author",  "") or ""
            result["metadata"]["subject"] = m.get("Subject", "") or ""
            result["metadata"]["creator"] = m.get("Creator", "") or ""

        all_sections: list[str] = []

        for i, page in enumerate(pdf.pages, start=1):
            raw_text  = page.extract_text() or ""
            tables:list[list[list[str]]] = []

            for tbl in (page.extract_tables() or []):
                tables.append(
                    [[str(cell) if cell is not None else "" for cell in row] for row in tbl]
                )

            # Decide whether OCR is needed for this page
            needs_ocr = force_ocr or (
                len(raw_text.strip()) < _MIN_TEXT_CHARS and not tables
            )

            if needs_ocr and _ocr_available():
                ocr_text = _ocr_page(str(path), i)
                if ocr_text.strip():
                    raw_text = ocr_text
                    ocr_page_nums.append(i)

            result["content"].append(
                {
                    "page":   i,
                    "text":   raw_text,
                    "tables": tables,
                    "ocr":    i in ocr_page_nums,
                }
            )

            # Build full-text section
            section = f"[Page {i}]" + (" [OCR]" if i in ocr_page_nums else "")
            if raw_text:
                section += f"\n{raw_text}"
            for t_i, tbl in enumerate(tables, start=1):
                section += f"\n[Table {t_i}]\n"
                section += "\n".join(" | ".join(row) for row in tbl)
            all_sections.append(section)

    result["full_text"] = "\n\n".join(all_sections)

    # Summarise which extraction method was used
    n = len(ocr_page_nums)
    total = result["metadata"]["pages"]
    if n == 0:
        result["metadata"]["method"] = "text"
    elif n == total:
        result["metadata"]["method"] = "ocr"
    else:
        result["metadata"]["method"] = f"mixed ({n}/{total} pages OCR)"

    return result
