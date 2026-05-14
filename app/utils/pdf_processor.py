"""
pdf_processor.py
----------------
Responsible for turning an uploaded study-material file (PDF or TXT) into a
clean list of text chunks that the retriever can index.

Pipeline:
    raw file  ->  extract text  ->  clean text  ->  chunk into ~500 word pieces

Used by the chatbot upload endpoint (app/api/chatbot.py).
"""

import os
import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Try to import PyMuPDF (the package is called PyMuPDF, the module is `fitz`).
# We import lazily so the rest of the Flask/FastAPI app still boots even if
# PyMuPDF is not installed yet (the user will be told to install it).
try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except Exception as e:  # pragma: no cover - import-time guard
    fitz = None
    _HAS_FITZ = False
    logger.warning("PyMuPDF (fitz) is not installed: %s", e)


# Allowed upload extensions for the RAG chatbot.
ALLOWED_EXTENSIONS = {".pdf", ".txt"}


def is_allowed_file(filename: str) -> bool:
    """Return True if the filename ends with a supported extension."""
    return os.path.splitext(filename.lower())[1] in ALLOWED_EXTENSIONS


def extract_pdf_text(file_path: str) -> str:
    """Extract all text from a PDF file using PyMuPDF (fitz)."""
    if not _HAS_FITZ:
        raise RuntimeError(
            "PyMuPDF is not installed. Run: pip install PyMuPDF"
        )
    text_parts: List[str] = []
    # fitz.open returns a document; iterate page-by-page so big PDFs stream.
    with fitz.open(file_path) as doc:
        for page in doc:
            text_parts.append(page.get_text("text") or "")
    return "\n".join(text_parts)


def extract_txt_text(file_path: str) -> str:
    """Read a plain-text file with a safe utf-8 fallback."""
    # 'errors=ignore' drops any byte that cannot be decoded so the chatbot
    # never crashes on weird characters from random study notes.
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_text(file_path: str) -> str:
    """Dispatch to PDF or TXT extractor based on file extension."""
    ext = os.path.splitext(file_path.lower())[1]
    if ext == ".pdf":
        return extract_pdf_text(file_path)
    if ext == ".txt":
        return extract_txt_text(file_path)
    raise ValueError(f"Unsupported file type: {ext}")


# Pre-compiled regexes for the cleaning step.
_RE_UNREADABLE = re.compile(r"[^\x09\x0a\x0d\x20-\x7e\u00a0-\uffff]")  # keep printable
_RE_MULTI_NEWLINE = re.compile(r"\n\s*\n+")
_RE_MULTI_SPACE = re.compile(r"[ \t]+")
_RE_LINE_TRAIL = re.compile(r"[ \t]+\n")


def clean_text(text: str) -> str:
    """
    Normalize extracted text:
      - drop unreadable / non-printable bytes
      - collapse runs of spaces / tabs
      - collapse 3+ newlines into a single blank line (paragraph break)
      - strip leading / trailing whitespace
    """
    if not text:
        return ""
    text = _RE_UNREADABLE.sub(" ", text)
    text = _RE_LINE_TRAIL.sub("\n", text)
    text = _RE_MULTI_SPACE.sub(" ", text)
    text = _RE_MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def chunk_text(
    text: str,
    chunk_words: int = 500,
    overlap_words: int = 100,
) -> List[str]:
    """
    Split cleaned text into overlapping word-windows.

    chunk_words   - target size of each chunk (default 500 words)
    overlap_words - words shared with the previous chunk (default 100)

    Overlap is important for RAG: it prevents an answer from being cut in
    half across two chunks.
    """
    if not text:
        return []
    words = text.split()
    if not words:
        return []
    if chunk_words <= 0:
        chunk_words = 500
    if overlap_words < 0 or overlap_words >= chunk_words:
        overlap_words = max(0, chunk_words // 5)

    step = chunk_words - overlap_words
    chunks: List[str] = []
    i = 0
    while i < len(words):
        piece = words[i : i + chunk_words]
        if not piece:
            break
        chunks.append(" ".join(piece))
        if i + chunk_words >= len(words):
            break
        i += step
    return chunks


def process_file(file_path: str) -> Tuple[str, List[str]]:
    """
    High-level helper used by the upload route.
    Returns: (file_name, list_of_chunks)
    """
    file_name = os.path.basename(file_path)
    raw = extract_text(file_path)
    cleaned = clean_text(raw)
    chunks = chunk_text(cleaned, chunk_words=500, overlap_words=100)
    logger.info("Processed %s -> %d chunks", file_name, len(chunks))
    return file_name, chunks
