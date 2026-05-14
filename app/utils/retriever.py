"""
retriever.py
------------
Tiny in-memory Retrieval-Augmented Generation (RAG) index for the
E-Shiksha chatbot.

Why TF-IDF + cosine similarity?
  - 100% offline, no embeddings download
  - works on CPU only
  - good enough for hackathon-scale single-document Q&A

Public API:
    add_file(file_name, chunks)                  add a new uploaded file
    retrieve(question, top_k)                    get most relevant chunks + score
    has_content()                                has anything been uploaded?
    clear()                                      wipe everything (for /clear route)
    list_files()                                 filenames currently in the index
    is_general_pdf_question(question, mode)      detect summary/overview questions
    get_context_for_question(question, mode)     smart context builder
"""

import logging
import threading
from typing import List, Tuple, Dict

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# Below this max cosine similarity we treat the result as "not in material".
# Tuned for short academic chunks; can be raised if hallucinations slip through.
SIMILARITY_THRESHOLD: float = 0.10

# Module-level store. A single uvicorn worker keeps everything in RAM, which
# is fine for a hackathon demo. Protected by a lock so concurrent /upload and
# /chat calls don't race.
_lock = threading.Lock()
_store: Dict[str, object] = {
    "chunks": [],          # List[str]   all chunks across all uploaded files
    "sources": [],         # List[str]   parallel list of file names per chunk
    "files": [],           # List[str]   unique uploaded file names
    "vectorizer": None,    # fitted TfidfVectorizer
    "matrix": None,        # sparse tf-idf matrix of shape (n_chunks, vocab)
}


def _rebuild_index() -> None:
    """Re-fit the TF-IDF vectorizer over the current chunk list."""
    chunks = _store["chunks"]
    if not chunks:
        _store["vectorizer"] = None
        _store["matrix"] = None
        return
    # Simple English-friendly TF-IDF: lowercase, drop stop words, allow
    # unigrams + bigrams so short queries like "newton law" match better.
    # When there is only one chunk (tiny upload), max_df=0.95 would resolve
    # to < 1 document and sklearn raises ValueError, so we relax it.
    max_df = 1.0 if len(chunks) < 3 else 0.95
    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        max_df=max_df,
        min_df=1,
    )
    matrix = vectorizer.fit_transform(chunks)
    _store["vectorizer"] = vectorizer
    _store["matrix"] = matrix
    logger.info(
        "Retriever index rebuilt: %d chunks, vocab=%d",
        len(chunks),
        len(vectorizer.vocabulary_),
    )


def add_file(file_name: str, chunks: List[str]) -> int:
    """
    Add chunks for a newly uploaded file and rebuild the index.
    Returns the number of chunks that were added.
    """
    if not chunks:
        return 0
    with _lock:
        _store["chunks"].extend(chunks)
        _store["sources"].extend([file_name] * len(chunks))
        if file_name not in _store["files"]:
            _store["files"].append(file_name)
        _rebuild_index()
        return len(chunks)


def clear() -> None:
    """Forget every uploaded file and reset the index."""
    with _lock:
        _store["chunks"] = []
        _store["sources"] = []
        _store["files"] = []
        _store["vectorizer"] = None
        _store["matrix"] = None
    logger.info("Retriever store cleared")


def has_content() -> bool:
    """True if at least one file has been uploaded and indexed."""
    return bool(_store["chunks"]) and _store["matrix"] is not None


def list_files() -> List[str]:
    """Return the list of uploaded file names currently in memory."""
    return list(_store["files"])


def retrieve(question: str, top_k: int = 4) -> Tuple[List[str], List[str], float]:
    """
    Find the most relevant chunks for `question`.

    Returns a tuple:
        ( top_chunks,        list of chunk strings, ordered best-first
          top_sources,       parallel list of file names
          best_similarity )  highest cosine similarity score (0..1)

    If nothing has been uploaded the tuple is ([], [], 0.0).
    """
    if not question or not question.strip():
        return [], [], 0.0
    if not has_content():
        return [], [], 0.0

    vectorizer: TfidfVectorizer = _store["vectorizer"]  # type: ignore[assignment]
    matrix = _store["matrix"]
    chunks: List[str] = _store["chunks"]        # type: ignore[assignment]
    sources: List[str] = _store["sources"]      # type: ignore[assignment]

    q_vec = vectorizer.transform([question])
    sims = cosine_similarity(q_vec, matrix)[0]   # shape: (n_chunks,)
    if sims.size == 0:
        return [], [], 0.0

    # argsort descending; cap at top_k and at number of chunks available.
    k = max(1, min(top_k, sims.size))
    top_idx = np.argsort(-sims)[:k]
    top_chunks = [chunks[i] for i in top_idx]
    top_sources = [sources[i] for i in top_idx]
    best = float(sims[top_idx[0]])
    return top_chunks, top_sources, best


# ---------------------------------------------------------------------------
# General / summary question detection
# ---------------------------------------------------------------------------

# Phrases that signal the student is asking about the PDF as a whole,
# not about a specific keyword found in the text.
_GENERAL_PHRASES: Tuple[str, ...] = (
    "main topic",
    "this pdf",
    "this document",
    "uploaded material",
    "uploaded document",
    "this chapter",
    "this file",
    "summarize",
    "summarise",
    "summary",
    "important points",
    "key points",
    "key takeaways",
    "explain this",
    "explain in simple",
    "simple words",
    "exam answer",
    "give exam answer",
    "overview",
    "what is this about",
    "what is this file",
    "notes",
    "short notes",
    "what does this pdf",
    "what does the pdf",
    "what does the document",
    "topics covered",
    "what are the main",
)

# These response modes always imply a general / whole-document question.
_GENERAL_MODES: Tuple[str, ...] = ("summary", "summarize", "summarise")


def is_general_pdf_question(question: str, mode: str = None) -> bool:  # type: ignore[assignment]
    """
    Return True when the question is about the PDF as a whole rather than
    a specific keyword.

    Detection logic:
      1. If `mode` is a summary/overview mode, return True immediately.
      2. If the lowercased question contains any of the _GENERAL_PHRASES.

    Args:
        question: The student's raw question string.
        mode:     Optional response-mode string from the request (e.g. "summary").
    """
    if mode and mode.strip().lower() in _GENERAL_MODES:
        return True
    q_lower = (question or "").lower()
    return any(phrase in q_lower for phrase in _GENERAL_PHRASES)


# ---------------------------------------------------------------------------
# Smart context builder
# ---------------------------------------------------------------------------

def get_context_for_question(
    question: str,
    mode: str = None,  # type: ignore[assignment]
    top_k: int = 5,
) -> Tuple[List[str], List[str], float, bool]:
    """
    Build the best context for a student question, handling both general
    (summary/overview) questions and specific keyword questions correctly.

    Returns a 4-tuple:
        chunks       - ordered list of context chunk strings
        sources      - parallel list of source file names
        best_sim     - highest TF-IDF cosine similarity score found
        is_general   - True when the general-question path was taken

    Debug output is printed to stdout so it is visible in the server log
    during hackathon testing.
    """
    chunks: List[str] = _store["chunks"]   # type: ignore[assignment]
    sources: List[str] = _store["sources"] # type: ignore[assignment]

    total_chunks = len(chunks)
    print(f"[Retriever] Total chunks loaded: {total_chunks}")

    if not has_content():
        print("[Retriever] No content uploaded.")
        return [], [], 0.0, False

    general = is_general_pdf_question(question, mode)
    print(f"[Retriever] Question type: {'GENERAL' if general else 'SPECIFIC'}")

    if general:
        # --- General / summary path -------------------------------------------
        # Use the first 3 chunks (introduction / beginning of the document) …
        n_head = min(3, total_chunks)
        head_chunks = chunks[:n_head]
        head_sources = sources[:n_head]

        # … plus up to 2 additional chunks from TF-IDF retrieval.
        tfidf_chunks, tfidf_sources, best_sim = retrieve(question, top_k=2)

        # Merge, de-duplicating by content identity.
        seen_content: set = set()
        merged_chunks: List[str] = []
        merged_sources: List[str] = []

        for c, s in list(zip(head_chunks, head_sources)) + list(zip(tfidf_chunks, tfidf_sources)):
            key = c[:120]  # first 120 chars as a cheap identity key
            if key not in seen_content:
                seen_content.add(key)
                merged_chunks.append(c)
                merged_sources.append(s)

        # For summary/important-points modes grab a few extra chunks for richer context.
        mode_lower = (mode or "").strip().lower()
        if mode_lower in ("summary", "summarize", "summarise", "important points", "important_points"):
            extra_end = min(6, total_chunks)
            for c, s in zip(chunks[n_head:extra_end], sources[n_head:extra_end]):
                key = c[:120]
                if key not in seen_content:
                    seen_content.add(key)
                    merged_chunks.append(c)
                    merged_sources.append(s)

        print(f"[Retriever] General path: selected {len(merged_chunks)} chunks, top TF-IDF sim={best_sim:.3f}")
        return merged_chunks, merged_sources, best_sim, True

    else:
        # --- Specific / keyword path ------------------------------------------
        top_chunks, top_sources, best_sim = retrieve(question, top_k=top_k)
        print(f"[Retriever] Specific path: selected {len(top_chunks)} chunks, top sim={best_sim:.3f}")
        return top_chunks, top_sources, best_sim, False
