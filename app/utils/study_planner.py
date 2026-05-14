"""
study_planner.py
----------------
Generates a calendar-based study plan from extracted PDF topics
and the student's learning profile.

100% offline — no Ollama required.
Logic adapts pace, revisions, and task types to the student profile.

Each plan event now includes:
  - paragraph   : raw text extract from the relevant PDF chunk
  - summary     : first 200 chars of the paragraph (quick overview)
  - key_points  : up to 4 extracted key sentences from the paragraph

Public API:
    generate_study_plan(topics, student_profile, chunks=None) -> List[Dict]
"""

import re
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

# Pace multiplier: how many topics the student can cover per day (relative)
_PACE = {"Beginner": 0.7, "Medium": 1.0, "Advanced": 1.4}

# Weekday numbers for light-day options (Monday=0 … Sunday=6)
_LIGHT_DAY_SETS = {
    "Sunday":              {6},
    "Saturday and Sunday": {5, 6},
    "No light days":       set(),
}

# Colour hints for calendar rendering (stored in event dict)
_TASK_COLOURS = {
    "Study":          "#4f46e5",
    "Revision":       "#7c3aed",
    "Quiz":           "#0891b2",
    "Mock Test":      "#dc2626",
    "Answer Writing": "#d97706",
    "Final Revision": "#059669",
}


def _get_paragraph_for_topic(topic: Dict, chunks: List[str]) -> str:
    """
    Retrieve the most relevant text paragraph for a topic from the PDF chunks.
    Uses chunk_indexes stored in the topic dict; falls back to summary field.
    """
    if not chunks:
        return topic.get("summary", "")
    idx_list = topic.get("chunk_indexes", [0])
    texts = []
    for idx in idx_list:
        if 0 <= idx < len(chunks):
            texts.append(chunks[idx].strip())
    return "\n".join(texts)[:1200] if texts else topic.get("summary", "")


def _extract_key_points(paragraph: str, n: int = 4) -> List[str]:
    """
    Extract up to `n` key sentences from a paragraph.
    Prefers sentences containing definition/importance keywords.
    Falls back to the first `n` sentences.
    """
    _KW = ("is", "are", "defined", "means", "refers", "used for",
           "important", "key", "formula", "theorem", "consist", "represent")
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraph) if len(s.strip()) > 20]
    # Prefer keyword-rich sentences
    preferred = [s for s in sentences if any(k in s.lower() for k in _KW)]
    combined  = preferred + [s for s in sentences if s not in preferred]
    return combined[:n]


def _pick_task_type(day_idx: int, total_days: int, level: str) -> str:
    """Decide what kind of study task to assign for a given day offset."""
    if total_days > 3 and day_idx == total_days - 1:
        return "Final Revision"
    if total_days > 4 and day_idx == total_days - 2:
        return "Mock Test"
    if day_idx % 4 == 3:                            # every 4th day → revision
        return "Revision"
    if level == "Advanced" and day_idx % 5 == 4:   # advanced gets more quizzes
        return "Quiz"
    return "Study"


def generate_study_plan(
    topics: List[Dict[str, Any]],
    student_profile: Dict[str, Any],
    chunks: Optional[List[str]] = None,   # PDF chunks for rich content
) -> List[Dict[str, Any]]:
    """
    Build a list of calendar events from topics + student profile.

    Adaptive rules:
    - Beginner : slower pace, more revision days
    - Advanced : faster pace, more quizzes and mock tests
    - Low confidence → extra revision blocks
    - High target (Top Score) → answer-writing practice added
    - Light days → 50% duration, only Revision tasks

    Args:
        topics:          Output of topic_extractor.extract_topics()
        student_profile: Dict saved via POST /api/tutor/save-profile

    Returns:
        List of calendar event dicts with keys:
        date, title, description, topics, duration_hours, task_type,
        difficulty, colour
    """
    # --- Unpack profile -------------------------------------------------------
    level      = student_profile.get("learning_level", "Medium")
    daily_hrs  = float(student_profile.get("daily_hours", 2))
    exam_str   = student_profile.get("exam_date", "")
    light_days = student_profile.get("light_days", "No light days")
    target     = student_profile.get("target", "Score Good Marks")
    confidence = int(student_profile.get("confidence", 3))

    # --- Date setup -----------------------------------------------------------
    today = date.today()
    try:
        exam_date = date.fromisoformat(exam_str)
    except Exception:
        exam_date = today + timedelta(days=14)          # 2-week fallback

    total_days = max(1, min(60, (exam_date - today).days))
    light_day_set = _LIGHT_DAY_SETS.get(light_days, set())

    # --- Pace adjustments -----------------------------------------------------
    pace = _PACE.get(level, 1.0)
    if confidence <= 2:
        pace *= 0.8     # low confidence → slower, more revision
    if target == "Top Score":
        pace *= 0.9     # top score → thorough coverage

    # Average hours per topic
    avg_hours = (
        sum(t["estimated_hours"] for t in topics) / len(topics)
    ) if topics else 1.0

    topics_per_day = max(1, int((daily_hrs / avg_hours) * pace))

    # --- Build event list -----------------------------------------------------
    events: List[Dict[str, Any]] = []
    topic_idx = 0           # pointer into topics list

    for day_offset in range(total_days):
        current_date = today + timedelta(days=day_offset)
        weekday  = current_date.weekday()           # 0=Mon … 6=Sun
        is_light = weekday in light_day_set
        task_type = _pick_task_type(day_offset, total_days, level)

        # Light days → forced Revision, half duration
        if is_light:
            task_type = "Revision"
            duration  = round(daily_hrs * 0.5, 1)
        else:
            duration = daily_hrs

        # --- Select topics for this day ---------------------------------------
        if task_type in ("Revision", "Final Revision", "Mock Test"):
            covered = [t["title"] for t in topics[:max(1, topic_idx)]]
            day_topics = (covered[-3:] if covered
                          else [t["title"] for t in topics[:3]])
            prefix_map = {
                "Revision":       "Review and reinforce",
                "Final Revision": "Final revision of all topics covered",
                "Mock Test":      "Full mock test covering",
            }
            description = f"{prefix_map[task_type]}: {', '.join(day_topics)}"

        elif task_type == "Quiz":
            covered = [t["title"] for t in topics[:max(1, topic_idx)]]
            day_topics = covered[-2:] if covered else (
                [topics[0]["title"]] if topics else ["General"]
            )
            description = f"Quiz: Self-test on {', '.join(day_topics)}"

        else:
            # Regular Study day — assign next N topics
            batch = topics[topic_idx: topic_idx + topics_per_day]
            if not batch and topics:
                topic_idx = 0               # wrap-around for long plans
                batch = topics[:topics_per_day]
            day_topics = [t["title"] for t in batch]
            topic_idx  = min(topic_idx + topics_per_day, len(topics))
            description = f"Study: {', '.join(day_topics)}"

        # Difficulty from the first topic in batch (or last studied)
        ref_idx    = min(max(topic_idx - 1, 0), len(topics) - 1)
        difficulty = topics[ref_idx]["difficulty"] if topics else "Medium"

        # ── Enrich event with PDF content (paragraph, summary, key_points) ──
        # For Study days: fetch paragraph from the first topic's chunk.
        # For Revision/Quiz/Mock days: combine summaries of covered topics.
        paragraph   = ""
        summary_txt = ""
        key_points: List[str] = []

        if chunks is not None and task_type == "Study":
            ref_topic = topics[ref_idx] if topics else {}
            paragraph = _get_paragraph_for_topic(ref_topic, chunks)
            summary_txt = paragraph[:200].strip()
            if len(paragraph) > 200:
                summary_txt += "…"
            key_points = _extract_key_points(paragraph, n=4)
        elif chunks is not None:
            # For non-study days, pull summaries from covered topics
            covered_topics = [t for t in topics if t["title"] in day_topics]
            paras = [_get_paragraph_for_topic(t, chunks) for t in covered_topics[:2]]
            paragraph   = "\n\n".join(paras)
            summary_txt = paragraph[:200].strip() + ("…" if len(paragraph) > 200 else "")
            key_points  = _extract_key_points(paragraph, n=3)

        event_id = f"event_{len(events) + 1}"
        events.append({
            "id":             event_id,
            "date":           current_date.isoformat(),
            "title":          f"{task_type}: {day_topics[0] if day_topics else 'Study'}",
            "description":    description,
            "topics":         day_topics,
            "duration_hours": duration,
            "task_type":      task_type,
            "difficulty":     difficulty,
            "colour":         _TASK_COLOURS.get(task_type, "#4f46e5"),
            # Rich content fields for the planner day-detail modal
            "paragraph":      paragraph,
            "summary":        summary_txt,
            "key_points":     key_points,
            "completed":      False,
        })

    # --- Top Score extra: answer-writing practice in last 20% of plan --------
    if target == "Top Score" and total_days >= 5:
        n_extra = max(1, total_days // 5)
        for i in range(n_extra):
            idx = len(events) - n_extra + i
            if 0 <= idx < len(events):
                events[idx]["description"] += " + Answer writing practice"
                events[idx]["task_type"]    = "Answer Writing"
                events[idx]["colour"]       = _TASK_COLOURS["Answer Writing"]

    return events
