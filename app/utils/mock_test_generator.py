"""
mock_test_generator.py
----------------------
Generate 10 MCQ questions from the uploaded study material.

Strategy:
  1. Try Ollama (llama3.2:3b) with a strict JSON prompt.
  2. If Ollama is unavailable or returns bad JSON, use the rule-based fallback.

Public API:
    generate_mock_test_from_context(chunks, topics) -> List[Dict]
"""

import re
import json
import logging
import random
from typing import List, Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)

# ── Ollama config (same as ai_tutor.py) ─────────────────────────────────────
OLLAMA_URL     = "http://localhost:11434/api/generate"
OLLAMA_MODEL   = "llama3.2:3b"
OLLAMA_TIMEOUT = 120   # seconds — MCQ generation can be slow

# Words that signal a sentence is a good source for a definition question
_DEF_KEYWORDS = ("is", "are", "refers to", "defined as",
                 "consists of", "used for", "means", "represents",
                 "describes", "enables", "allows", "provides")


# ── Context selection ────────────────────────────────────────────────────────

def _select_context(chunks: List[str]) -> str:
    """
    Pick up to ~3000 characters of context from the uploaded chunks.
    Use the first 4 chunks + evenly-spaced samples from the rest so the
    model sees a broad cross-section of the material.
    """
    if not chunks:
        return ""
    selected = list(chunks[:4])                       # first 4 chunks always
    if len(chunks) > 4:
        step = max(1, len(chunks) // 4)
        for i in range(4, len(chunks), step):
            selected.append(chunks[i])

    # Combine and cap at 3000 chars to stay within Ollama's context window
    combined = "\n\n".join(c.strip() for c in selected if c.strip())
    return combined[:3000]


# ── Ollama-based generator ───────────────────────────────────────────────────

_MCQ_PROMPT = """You are E-Shiksha, an offline exam question generator.

Generate exactly 10 unique multiple choice questions using ONLY the uploaded study material context below.

Rules:
1. Use only the provided context. Do not use outside knowledge.
2. Do not hallucinate. If information is not in the context, skip it.
3. Each question must have exactly 4 options: A, B, C, D.
4. Only one option must be correct.
5. Include correct_answer as A, B, C, or D.
6. Include a short explanation based only on the context.
7. Include topic name from the topics list.
8. Avoid duplicate questions.
9. Make questions useful for exam preparation.
10. Return ONLY a valid JSON array. No markdown. No extra text outside JSON.

Context:
{context}

Topics:
{topics}

Return JSON format exactly like this:
[
  {{
    "id": "q1",
    "question": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "correct_answer": "A",
    "explanation": "...",
    "topic": "..."
  }}
]"""


def _call_ollama(context: str, topics: List[str]) -> Optional[List[Dict]]:
    """
    Send prompt to Ollama. Returns parsed list of MCQ dicts or None on failure.
    Debug logs show model used and whether it succeeded.
    """
    topics_str = ", ".join(t["title"] if isinstance(t, dict) else str(t)
                           for t in topics[:10])
    prompt = _MCQ_PROMPT.format(context=context, topics=topics_str)
    payload = {
        "model":   OLLAMA_MODEL,
        "prompt":  prompt,
        "stream":  False,
        "options": {"temperature": 0.3, "num_predict": 2048},
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT)
        resp.raise_for_status()
        raw = (resp.json().get("response") or "").strip()

        # Strip markdown fences if present
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()

        # Find JSON array boundaries
        start = raw.find("[")
        end   = raw.rfind("]")
        if start != -1 and end > start:
            raw = raw[start: end + 1]

        questions = json.loads(raw)
        if isinstance(questions, list) and questions:
            logger.info("[MockTest] Ollama generated %d questions", len(questions))
            print(f"[MockTest] ✅ Ollama generated {len(questions)} MCQs | model={OLLAMA_MODEL}")
            return questions

    except requests.exceptions.ConnectionError:
        logger.warning("[MockTest] Ollama not reachable — using rule-based fallback")
        print("[MockTest] ⚠️  Ollama not running — falling back to rule-based MCQ generator")
    except Exception as exc:
        logger.warning("[MockTest] Ollama error: %s — using fallback", exc)
        print(f"[MockTest] ⚠️  Ollama error: {exc} — using fallback")
    return None


# ── Rule-based fallback MCQ generator ───────────────────────────────────────

def _extract_keywords(text: str, n: int = 20) -> List[str]:
    """Return the most frequent content words (4+ chars) from text."""
    words = re.findall(r"[a-zA-Z]{4,}", text.lower())
    stop  = {"that", "this", "with", "from", "have", "been", "they",
             "their", "which", "when", "what", "will", "each", "also",
             "more", "than", "some", "into", "about", "used", "like"}
    freq: Dict[str, int] = {}
    for w in words:
        if w not in stop:
            freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:n]]


def _fallback_mcqs(chunks: List[str], topics: List[str]) -> List[Dict]:
    """
    Rule-based MCQ generator.

    For each definition-like sentence found in the chunks:
      - Sentence:  "X is/are/refers to Y"
      - Question:  "What is X?" or "What does X refer to?"
      - Correct:   Y (truncated to ~50 chars)
      - Distractors: 3 random keywords from the material

    Returns up to 10 question dicts in the standard MCQ format.
    """
    full_text  = " ".join(chunks)
    keywords   = _extract_keywords(full_text)
    topic_names = [t["title"] if isinstance(t, dict) else str(t) for t in topics]

    sentences: List[str] = []
    for chunk in chunks:
        for sent in re.split(r"(?<=[.!?])\s+", chunk):
            sent = sent.strip()
            if 20 < len(sent) < 300:
                sentences.append(sent)

    questions: List[Dict] = []
    seen_questions: set   = set()
    q_idx = 1

    random.shuffle(sentences)

    for sent in sentences:
        if q_idx > 10:
            break

        # Match  "X is/are/refers to/defined as Y"
        for kw in _DEF_KEYWORDS:
            pattern = rf"(.{{5,60}}?)\s+{re.escape(kw)}\s+(.{{10,120}})"
            m = re.match(pattern, sent, re.IGNORECASE)
            if m:
                subject   = m.group(1).strip().rstrip(",;:")
                predicate = m.group(2).strip().rstrip(".,;:")
                if len(predicate) > 60:
                    predicate = predicate[:57] + "..."

                question_text = f"What is '{subject}'?"
                if question_text in seen_questions:
                    continue
                seen_questions.add(question_text)

                # Build 3 distractor answers from keywords
                distractors = [
                    k.capitalize() for k in keywords
                    if k not in predicate.lower() and k not in subject.lower()
                ][:3]
                while len(distractors) < 3:
                    distractors.append("Not mentioned in the material")

                # Shuffle correct answer into a random position
                opts = distractors[:3]
                correct_pos = random.randint(0, 3)
                opts.insert(correct_pos, predicate)
                letter_map = ["A", "B", "C", "D"]
                correct_letter = letter_map[correct_pos]

                topic = topic_names[q_idx % len(topic_names)] if topic_names else "General"

                questions.append({
                    "id":             f"q{q_idx}",
                    "question":       question_text,
                    "options":        {
                        "A": opts[0], "B": opts[1],
                        "C": opts[2], "D": opts[3],
                    },
                    "correct_answer": correct_letter,
                    "explanation":    f"According to the material: {subject} {kw} {predicate[:100]}.",
                    "topic":          topic,
                })
                q_idx += 1
                break   # one question per sentence

    logger.info("[MockTest] Fallback generated %d questions", len(questions))
    print(f"[MockTest] 📝 Rule-based fallback generated {len(questions)} MCQs")

    if not questions:
        # Last resort: topic-recognition questions
        for i, tn in enumerate(topic_names[:10]):
            questions.append({
                "id":             f"q{i+1}",
                "question":       f"Which of the following is a main topic in the uploaded material?",
                "options":        {
                    "A": tn,
                    "B": "Quantum Computing",
                    "C": "Ancient History",
                    "D": "Financial Markets",
                },
                "correct_answer": "A",
                "explanation":    f"'{tn}' is one of the key topics extracted from the uploaded document.",
                "topic":          tn,
            })
        if not questions:
            questions.append({
                "id": "q1",
                "question": "What type of document was uploaded for this mock test?",
                "options": {"A": "Study material", "B": "Recipe book",
                            "C": "Travel guide", "D": "Fiction novel"},
                "correct_answer": "A",
                "explanation": "The uploaded document is study material used to generate this test.",
                "topic": "General",
            })

    return questions[:10]


# ── Public API ───────────────────────────────────────────────────────────────

def generate_mock_test_from_context(
    chunks: List[str],
    topics: List[Any],
) -> List[Dict]:
    """
    Generate up to 10 MCQ questions from the uploaded study material.

    Tries Ollama first; falls back to rule-based generator if:
    - Ollama is not running, or
    - Ollama returns invalid / empty JSON.

    Args:
        chunks:  Text chunks from ACTIVE_SESSION["chunks"]
        topics:  Topic dicts from ACTIVE_SESSION["topics"]

    Returns:
        List of MCQ dicts with keys:
        id, question, options (dict A-D), correct_answer, explanation, topic
    """
    if not chunks:
        logger.warning("[MockTest] No chunks available — cannot generate MCQs")
        return []

    context = _select_context(chunks)
    logger.info("[MockTest] Context length=%d | topics=%d", len(context), len(topics))
    print(f"[MockTest] Generating MCQs | context={len(context)} chars | topics={len(topics)}")

    # Try Ollama
    questions = _call_ollama(context, topics)

    # Validate Ollama result has required keys
    if questions:
        valid = [
            q for q in questions
            if isinstance(q, dict)
            and q.get("question")
            and isinstance(q.get("options"), dict)
            and len(q.get("options", {})) >= 2
            and q.get("correct_answer")
        ]
        if len(valid) >= 3:
            # Ensure IDs are set
            for i, q in enumerate(valid):
                q["id"] = q.get("id") or f"q{i+1}"
            return valid[:10]
        logger.warning("[MockTest] Ollama result invalid — switching to fallback")
        print("[MockTest] Ollama result had insufficient valid questions — using fallback")

    # Fallback
    return _fallback_mcqs(chunks, topics)
