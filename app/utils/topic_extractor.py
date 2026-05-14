"""
topic_extractor.py
------------------
Offline, rule-based topic extractor for E-Shiksha.

Detects headings from uploaded PDF/TXT content and creates structured
topic objects — no AI / Ollama needed.  Works 100% offline.

Public API:
    extract_topics(text, chunks) -> List[Dict]
"""

import re
from typing import List, Dict, Any

# Keywords that indicate technically complex / hard content
_HARD_KEYWORDS = (
    "algorithm", "theorem", "formula", "equation", "proof",
    "calculus", "matrix", "integration", "differentiation",
    "complexity", "recursive", "polynomial", "eigenvalue",
    "derivative", "integral", "probability", "statistical",
)

# Compiled patterns that identify heading lines
_HEADING_PATTERNS = [
    re.compile(r'^[A-Z][A-Z\s\-:]{4,}$'),                          # ALL CAPS
    re.compile(r'^\d+\.\s+[A-Z]\w+'),                               # 1. Title
    re.compile(r'^\d+\.\d+\.?\s+[A-Z]\w+'),                        # 1.1 Title
    re.compile(r'^(Unit|Chapter|Module|Section|Part)\s+\d+',
               re.IGNORECASE),                                       # Unit 1
]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _estimate_difficulty(text: str) -> str:
    """Return 'Easy', 'Medium', or 'Hard' based on text content."""
    t = text.lower()
    hard_hits = sum(1 for kw in _HARD_KEYWORDS if kw in t)
    words = len(text.split())
    if hard_hits >= 3 or words > 400:
        return "Hard"
    if hard_hits >= 1 or words > 150:
        return "Medium"
    return "Easy"


def _estimate_hours(difficulty: str) -> float:
    """Return estimated study hours for a given difficulty level."""
    return {"Easy": 0.5, "Medium": 1.0, "Hard": 2.0}.get(difficulty, 1.0)


def _detect_headings(text: str) -> List[str]:
    """
    Scan text line-by-line and return lines that look like headings.

    Detects:
    - ALL-CAPS lines
    - Numbered sections (1. / 1.1)
    - Unit / Chapter / Module / Section prefixes
    - Short title-like lines (2–10 words, starts capital, no punctuation)
    """
    headings: List[str] = []
    seen: set = set()

    for raw in text.split('\n'):
        line = raw.strip()
        if not line or len(line) > 120:
            continue

        matched = any(p.match(line) for p in _HEADING_PATTERNS)

        if not matched:
            # Fallback: short title-like line
            words = line.split()
            if (2 <= len(words) <= 10
                    and line[0].isupper()
                    and not any(c in line for c in (',', ';', '?', '!', ':'))):
                matched = True

        if matched and line not in seen:
            seen.add(line)
            headings.append(line)

    return headings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_topics(text: str, chunks: List[str]) -> List[Dict[str, Any]]:
    """
    Extract a structured topic list from uploaded file content.

    Strategy:
    1. Detect headings from raw text.
    2. If fewer than 2 headings found, fall back to chunk-based topics.
    3. For each topic, assign a relevant chunk, difficulty, and hours.

    Returns a list of dicts:
        topic_id, title, summary, chunk_indexes, difficulty, estimated_hours
    """
    headings = _detect_headings(text)
    topics: List[Dict[str, Any]] = []

    if len(headings) >= 2:
        # --- Heading-based topics (max 20) -----------------------------------
        for i, heading in enumerate(headings[:20]):
            chunk_idx = min(i, len(chunks) - 1) if chunks else 0
            sample    = chunks[chunk_idx] if chunks else ""
            diff      = _estimate_difficulty(sample)
            topics.append({
                "topic_id":       f"T{i + 1}",
                "title":          heading,
                "summary":        (sample[:200] + "…") if len(sample) > 200 else sample,
                "chunk_indexes":  [chunk_idx],
                "difficulty":     diff,
                "estimated_hours": _estimate_hours(diff),
            })
    else:
        # --- Chunk-based fallback (max 15) -----------------------------------
        for i, chunk in enumerate(chunks[:15]):
            diff = _estimate_difficulty(chunk)
            topics.append({
                "topic_id":       f"T{i + 1}",
                "title":          f"Topic {i + 1}",
                "summary":        (chunk[:200] + "…") if len(chunk) > 200 else chunk,
                "chunk_indexes":  [i],
                "difficulty":     diff,
                "estimated_hours": _estimate_hours(diff),
            })

    return topics
