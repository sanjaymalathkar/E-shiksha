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
        "## Explanation\n(2-3 sentences expanding on the key points)\n"
        "## Example\n(only if the context contains one, else write: "
        f"\"{NO_EXAMPLE_MESSAGE}\")\n"
        "## Conclusion\n(one short closing sentence)"
    ),
    "summary": (
        "Summarize the uploaded study material. "
        "Output 5 to 8 short bullet points covering the main topics and key ideas. "
        "Each bullet must be one short, clear line. "
        "No introduction sentence, no conclusion paragraph. Use bullet points only."
    ),
    "important_points": (
        "Extract Important Points. "
        "List the 6-10 most important facts, definitions, or concepts from the context. "
        "Use bullet points. Each point must be short and exam-focused. "
        "Bold the key term in each bullet where applicable."
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
        "summarise": "summary",
        "summary": "summary",
        "important_points": "important_points",
        "important": "important_points",
        "key_points": "important_points",
        "keypoints": "important_points",
    }
    return aliases.get(m, "normal")


# ---- Prompt template -------------------------------------------------------
# Improved tutor-style prompt. Rules force the model to stay grounded in
# `context` while also correctly handling summary / overview questions.
PROMPT_TEMPLATE = """You are E-Shiksha, an offline AI tutor for students.

Answer only using the uploaded study material context provided below.

Rules:
1. Use only the provided context. Do not use outside knowledge.
2. Do not guess. Do not invent facts. Do not hallucinate.
3. If the question is specific and the answer is not present in context, say EXACTLY:
   "I could not find this information in the uploaded study material."
4. If the question asks for a summary, main topic, important points, or overview,
   summarize the provided context — do not say the information is missing.
5. Explain in simple, student-friendly English.
6. Make answers exam-focused: highlight definitions, key points, and examples.
7. Use bullet points and markdown headings (## Heading) for clarity.
8. Keep the answer clear and useful.
9. After the answer, ALWAYS add one short follow-up question on a new line starting with:
   "Follow-up:"
   Example: Follow-up: Do you want a simple explanation, example, or exam answer format?

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
    is_general: bool = False,
) -> Tuple[bool, str]:
    """
    Heuristic guard that catches answers the model produced without using
    the retrieved context.

    Args:
        answer:         The generated answer text.
        context_chunks: The chunks passed to the model as context.
        min_overlap:    Minimum token-overlap fraction required for a specific question.
        is_general:     When True (summary / overview questions) the overlap threshold
                        is relaxed so the model's synthesised summary is not rejected.

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

    # For general/summary questions the model paraphrases across many chunks,
    # so the naive overlap ratio is naturally lower.  Use a relaxed threshold.
    effective_threshold = 0.08 if is_general else min_overlap
    if overlap < effective_threshold:
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
