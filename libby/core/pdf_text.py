"""PDF text extraction using pypdf."""

from pathlib import Path

from pypdf import PdfReader


def extract_first_page_text(pdf_path: Path) -> str:
    """Extract text from the first page of a PDF.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Text content of the first page, or empty string if extraction fails.
    """
    try:
        reader = PdfReader(pdf_path)
        if not reader.pages:
            return ""
        return reader.pages[0].extract_text() or ""
    except Exception:
        return ""