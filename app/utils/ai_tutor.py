"""
ai_tutor.py
-----------
Builds the strict tutor-style RAG prompt and dispatches generation to the
configured backend (local Ollama by default, optionally an online API).

If the configured backend is not reachable we do NOT crash the app; we
return a friendly fallback string that the chatbot route forwards to the UI.
"""

import os
import re
import logging
from typing import List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ---- Backend selection -----------------------------------------------------
# AI_MODE picks the generation backend.
#   "ollama" (default) -> local Ollama running on http://localhost:11434
#   "online"           -> use the existing online model code (Gemini if a
#                         GOOGLE_API_KEY is set). Kept separate so the
#                         offline hackathon demo never accidentally calls
#                         the internet.
AI_MODE = os.getenv("AI_MODE", "ollama").strip().lower()

# ---- Configuration ---------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

# ---- User-visible fallback messages ----------------------------------------
NO_FILE_MESSAGE = "Please upload study material first."
NOT_IN_MATERIAL_MESSAGE = (
    "I could not find this information in the uploaded study material."
)
NO_EXAMPLE_MESSAGE = (
    "The uploaded material does not provide an example for this topic."
)
OLLAMA_UNAVAILABLE_MESSAGE = (
    "Local AI model is not available. "
    "Please start Ollama and pull llama3.2:3b."
)
ONLINE_UNAVAILABLE_MESSAGE = (
    "Online AI model is not configured. "
    "Set GOOGLE_API_KEY or switch AI_MODE to 'ollama'."
)

# ---- Response modes --------------------------------------------------------
# Each mode injects a precise formatting recipe under "Response Mode:".
# These match the dropdown options in the chatbot UI.
RESPONSE_MODES = {
    "normal": (
        "Normal Answer. Reply like a friendly tutor. "
        "Start with a short heading (## Heading), then 3-5 short bullets "
        "based only on the context. Avoid long paragraphs."
    ),
    "simple": (
        "Explain Simply. Use very easy English, short sentences, and "
        "everyday words a beginner student can understand. "
        "Start with a one-line summary, then 3-4 simple bullets. "
        "Do not use difficult or technical words unless absolutely needed."
    ),
    "example": (
        "Explain with Example. Give an example ONLY if the context clearly "
        "contains one. Format: a short explanation, then an '## Example' "
        "heading with the example from the material. "
        "If the context does NOT contain an example, reply EXACTLY: "
        f"\"{NO_EXAMPLE_MESSAGE}\""
    ),
    "exam": (
        "Give Exam Answer. Use this exact structure with markdown headings:\n"
        "## Definition\n(one or two sentences from the context)\n"
        "## Key Points\n(4-6 short bullets)\n"
        "## Example\n(only if the context contains one, else write: "
        f"\"{NO_EXAMPLE_MESSAGE}\")\n"
        "## Conclusion\n(one short closing sentence)"
    ),
    "summary": (
        "Summarize. Output 5 to 7 short bullet points only. "
        "Each bullet must be one short line. No introduction, no conclusion, "
        "no paragraphs."
    ),
}


def normalize_mode(mode: Optional[str]) -> str:
    """Map any incoming mode string to one of RESPONSE_MODES keys."""
    if not mode:
        return "normal"
    m = mode.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "normal_answer": "normal",
        "normal": "normal",
        "explain_simply": "simple",
        "simple": "simple",
        "explain_with_example": "example",
        "example": "example",
        "give_exam_answer": "exam",
        "exam_answer": "exam",
        "exam": "exam",
        "summarize": "summary",
        "summary": "summary",
    }
    return aliases.get(m, "normal")


# ---- Prompt template -------------------------------------------------------
# Strict tutor-style prompt. The rules force the model to stay grounded in
# `context`. The "tutor behaviour" block makes answers feel like a real
# teacher talking to a student, not a generic LLM dump.
PROMPT_TEMPLATE = """You are E-Shiksha, an offline AI tutor for students.

Your only job is to help the student understand the uploaded study material.

Strict rules:
1. Use ONLY the given context from the uploaded file. Do not use outside knowledge.
2. Do not guess. Do not invent facts. Do not hallucinate.
3. If the answer is not present in the context, reply EXACTLY:
   "I could not find this information in the uploaded study material."
4. Do not answer questions that are unrelated to the uploaded material.

Tutor behaviour:
5. Talk like a friendly school/college teacher, not a generic AI.
6. Keep the answer SHORT and CLEAR. No long paragraphs.
7. Use markdown headings (## Heading) and bullet points (- item) so the
   answer is easy to scan.
8. Be exam-focused: highlight definitions, key points, and small examples
   that a student would write in an exam.
9. After the answer, ALWAYS add one short follow-up question on a new line
   that starts with the prefix "Follow-up:". Example:
   Follow-up: Do you want this in simple explanation, example, or exam answer format?

Follow the Response Mode below exactly for the layout.

Context:
{context}

Student Question:
{question}

Response Mode:
{mode}

Answer:"""


def build_prompt(context_chunks: List[str], question: str, mode: str) -> str:
    """Render the strict prompt with retrieved context + mode directive."""
    mode_key = normalize_mode(mode)
    mode_directive = RESPONSE_MODES[mode_key]
    # Separator makes it easier for the model to see chunk boundaries.
    context_block = "\n\n---\n\n".join(c.strip() for c in context_chunks if c.strip())
    if not context_block:
        context_block = "(no context available)"
    return PROMPT_TEMPLATE.format(
        context=context_block,
        question=question.strip(),
        mode=mode_directive,
    )


# ---- Answer validator ------------------------------------------------------
# Patterns that strongly suggest the model gave up or wandered out of context.
_REFUSAL_PATTERNS = (
    "as an ai language model",
    "i cannot",
    "i don't have access",
    "i do not have access",
    "outside the context",
    "outside of the context",
    "based on my training",
    "based on general knowledge",
    "i apologize",
)

_TOKEN_RE = re.compile(r"[a-z][a-z0-9]{3,}")  # words of 4+ chars, lowercased


def _tokens(text: str) -> set:
    """Return the set of content words (4+ chars, lowercased) in `text`."""
    return set(_TOKEN_RE.findall((text or "").lower()))


def validate_answer(
    answer: str,
    context_chunks: List[str],
    min_overlap: float = 0.18,
) -> Tuple[bool, str]:
    """
    Heuristic guard that catches answers the model produced without using
    the retrieved context.

    Returns:
        (is_valid, reason)
        - is_valid=True  -> answer can be shown to the student.
        - is_valid=False -> the route should replace `answer` with
                            NOT_IN_MATERIAL_MESSAGE.
    """
    if not answer or not answer.strip():
        return False, "empty"

    low = answer.lower()
    # The strict refusal lines are allowed (they are the system's own
    # NOT_IN_MATERIAL / NO_EXAMPLE messages).
    if NOT_IN_MATERIAL_MESSAGE.lower() in low or NO_EXAMPLE_MESSAGE.lower() in low:
        return True, "refusal-by-design"

    for pat in _REFUSAL_PATTERNS:
        if pat in low:
            return False, f"refusal-pattern:{pat}"

    # Token-overlap check: a grounded answer should share a reasonable
    # number of content words with the retrieved context.
    ans_tokens = _tokens(answer)
    ctx_tokens: set = set()
    for c in context_chunks:
        ctx_tokens |= _tokens(c)
    if not ans_tokens:
        return True, "too-short-to-judge"
    overlap = len(ans_tokens & ctx_tokens) / max(1, len(ans_tokens))
    if overlap < min_overlap:
        return False, f"low-overlap:{overlap:.2f}"
    return True, "ok"


# ---- Generation backends ---------------------------------------------------
def call_ollama(prompt: str) -> Optional[str]:
    """
    Send `prompt` to the local Ollama daemon.
    Returns the generated text on success, or None on any failure.
    Never raises - the route layer converts None into OLLAMA_UNAVAILABLE_MESSAGE.
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        # Low temperature => stay close to retrieved material, less creative.
        "options": {"temperature": 0.15, "num_predict": 1024},
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("response") or "").strip()
        return text or None
    except requests.exceptions.ConnectionError:
        logger.warning("Ollama not reachable at %s", OLLAMA_URL)
        return None
    except requests.exceptions.Timeout:
        logger.warning("Ollama request timed out after %ss", OLLAMA_TIMEOUT)
        return None
    except Exception as e:  # pragma: no cover - defensive
        logger.error("Ollama call failed: %s", e)
        return None


def call_online(prompt: str) -> Optional[str]:
    """
    Optional online backend (Gemini). Used only when AI_MODE='online'.
    Returns None if the API key is missing or the call fails - the route
    then surfaces ONLINE_UNAVAILABLE_MESSAGE so the demo never crashes.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    try:
        # Imported lazily so offline mode never touches the online SDK.
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content(prompt)
        text = (getattr(resp, "text", "") or "").strip()
        return text or None
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Online (Gemini) call failed: %s", e)
        return None


def generate_answer(prompt: str) -> Tuple[Optional[str], str]:
    """
    Dispatch to the configured backend.
    Returns (answer_or_none, unavailable_message_for_this_mode).
    """
    if AI_MODE == "online":
        return call_online(prompt), ONLINE_UNAVAILABLE_MESSAGE
    # Default and explicit "ollama" both use the local model.
    return call_ollama(prompt), OLLAMA_UNAVAILABLE_MESSAGE
