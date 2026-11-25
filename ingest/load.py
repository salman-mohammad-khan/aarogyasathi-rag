"""Turns a downloaded file into pages of plain text.

PDF: pypdf reads the text layer page by page, so every chunk later knows its page number for the citation.
HTML (WHO fact sheets): trafilatura keeps the main article text and drops menus, footers and cookie banners.
Scanned PDFs without a text layer give empty pages; they are reported, not guessed (no OCR in this version).
"""
from pathlib import Path

import trafilatura
from pypdf import PdfReader

from app.types import Page, Source


def load_pages(source: Source, path: Path) -> list[Page]:
    """Return the text of every page of one downloaded source."""
    if source.type == "pdf":
        reader = PdfReader(str(path))
        return [Page(source.id, number, page.extract_text() or "") for number, page in enumerate(reader.pages, 1)]
    html = path.read_text(encoding="utf-8", errors="replace")
    text = trafilatura.extract(html, include_tables=True, include_comments=False, favor_precision=True) or ""
    return [Page(source.id, 1, text)]
