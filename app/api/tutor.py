"""
tutor.py  —  Unified AI Tutor API for E-Shiksha
-------------------------------------------------
Single-file learning workflow:
  Upload PDF → Analyse → Student Profile → Calendar Plan → Chatbot

Routes (all under /api/tutor):
    POST /upload          Upload + analyse file, clear old session
    POST /save-profile    Save student learning profile
    POST /generate-plan   Generate personalised calendar study plan
    GET  /get-plan        Return current study plan
    POST /chat            Chat using latest uploaded file only
    POST /clear           Clear everything (file, plan, chat)
    GET  /status          Session status snapshot

ACTIVE_SESSION is module-level — safe for single-process hackathon demo.
Replace with Redis / DB for production multi-user deployments.
"""

import os
import uuid
import asyncio
import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Body
from pydantic import BaseModel

# Existing utilities
from app.utils import pdf_processor, retriever, ai_tutor
# New utilities created in this session
from app.utils.topic_extractor    import extract_topics
from app.utils.study_planner      import generate_study_plan
from app.utils.mock_test_generator import generate_mock_test_from_context

logger    = logging.getLogger(__name__)
router    = APIRouter(prefix="/api/tutor", tags=["tutor"])

# ---------------------------------------------------------------------------
# ACTIVE_SESSION — single in-memory store for the entire student session.
#
# File-specific fields are cleared on every new upload.
# Attendance, ranking, profile, and progress survive across file changes
# because they belong to the student, not to a specific uploaded PDF.
# ---------------------------------------------------------------------------
ACTIVE_SESSION: Dict[str, Any] = {
    # ── File / RAG ────────────────────────────────────────────────────────
    "file_id":         None,   # short uuid for the active file
    "filename":        None,   # original filename
    "raw_text":        "",     # full cleaned extracted text
    "chunks":          [],     # 500-word overlapping text chunks
    "topics":          [],     # structured topic list from topic_extractor
    "student_profile": {},     # learning profile (level, hours, exam date …)
    "study_plan":      [],     # calendar event dicts
    "chat_history":    [],     # [{question, answer}, ...]
    "mock_test":       [],     # generated MCQ question dicts
    "mock_test_result": {},    # {score, percentage, weak_topics, review}

    # ── Attendance ────────────────────────────────────────────────────────
    # Key = "YYYY-MM-DD", value = {status, timestamp}
    "attendance": {},

    # ── Ranking / gamification ────────────────────────────────────────────
    "ranking": {
        "points":     0,
        "level":      "Beginner Learner",
        "badge":      "Starter",
        "motivation": "Great start! Upload your study material to begin.",
        "rank":       "Bronze",
    },

    # ── Study progress ─────────────────────────────────────────────────────
    "progress": {
        "completed_tasks": 0,
        "total_tasks":     0,
        "quiz_score":      0,
        "study_streak":    0,
    },

    # ── Student profile details ────────────────────────────────────────────
    "profile": {
        "full_name":         "",
        "email":             "",
        "phone":             "",
        "class_or_semester": "",
        "department":        "",
        "college":           "",
        "preferred_language": "English",
        "learning_goal":     "",
        "daily_study_hours": 2,
        "exam_target":       "",
    },
}

_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
UPLOAD_DIR = os.path.join(_PROJECT_ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _reset_session() -> None:
    """
    Clear file-specific data from ACTIVE_SESSION and wipe the TF-IDF index.

    PRESERVES across file changes (they belong to the student, not the file):
      - attendance, ranking, progress, profile

    CLEARS (stale after new upload):
      - file_id, filename, raw_text, chunks, topics,
        student_profile, study_plan, chat_history
    """
    ACTIVE_SESSION.update({
        "file_id":          None,
        "filename":         None,
        "raw_text":         "",
        "chunks":           [],
        "topics":           [],
        "student_profile":  {},
        "study_plan":       [],
        "chat_history":     [],
        "mock_test":        [],     # clear old mock test — it was from old PDF
        "mock_test_result": {},     # clear old results
        # Reset task/mock counts (belong to old plan)
        "progress": {
            **ACTIVE_SESSION.get("progress", {}),
            "completed_tasks": 0,
            "total_tasks":     0,
            "mock_score":      0,
        },
    })
    retriever.clear()   # Remove old PDF from TF-IDF index
    logger.info("[Tutor] File session cleared — old PDF, plan, and chat removed")


# ── Ranking helpers ──────────────────────────────────────────────────────────

def _ranking_level(points: int) -> str:
    """Map total points to a learner level label."""
    if points < 50:   return "Beginner Learner"
    if points < 100:  return "Consistent Learner"
    if points < 200:  return "Smart Learner"
    return "Exam Warrior"

def _ranking_rank(points: int) -> str:
    """Map total points to a rank tier."""
    if points < 50:   return "Bronze"
    if points < 100:  return "Silver"
    if points < 200:  return "Gold"
    return "Platinum"

def _ranking_badge(points: int) -> str:
    """Map total points to a motivational badge."""
    if points < 50:   return "Starter"
    if points < 100:  return "Focus Builder"
    if points < 200:  return "Study Streak"
    return "Exam Warrior"

def _ranking_motivation(points: int) -> str:
    """Return a contextual motivation message based on points."""
    if points < 50:
        return "Great start! Complete today's task to improve your rank."
    if points < 100:
        return "You are building a strong study habit. Keep going!"
    if points < 200:
        return "Excellent consistency. Keep revising daily."
    return "Exam Warrior mode activated. Keep pushing!"

def _award_points(action: str, points: int) -> Dict[str, Any]:
    """
    Add points for an action and refresh ranking fields.
    Returns the updated ranking dict.

    Point awards:
      upload_material  : +10
      generate_plan    : +20
      complete_task    : +15
      mark_attendance  : +10
      ask_ai_tutor     : +2
    """
    r = ACTIVE_SESSION["ranking"]
    r["points"] += points
    p = r["points"]
    r["level"]      = _ranking_level(p)
    r["rank"]       = _ranking_rank(p)
    r["badge"]      = _ranking_badge(p)
    r["motivation"] = _ranking_motivation(p)

    # Debug log
    logger.info("[Ranking] action=%s | +%d pts | total=%d | rank=%s | badge=%s",
                action, points, p, r["rank"], r["badge"])
    print(f"[Ranking] action={action} | +{points} pts | total={p} | rank={r['rank']} | badge={r['badge']}")
    return dict(r)


# ---------------------------------------------------------------------------
# A. Upload + Analyse
# ---------------------------------------------------------------------------

@router.post("/upload")
async def tutor_upload(file: UploadFile = File(...)):
    """
    Step 1 — Upload a PDF or TXT study-material file.

    What happens:
    1. Old session is fully cleared (file, chunks, topics, plan, chat).
    2. File is saved to uploads/.
    3. Text is extracted, cleaned, chunked (500-word / 100-word overlap).
    4. Topics are extracted offline (rule-based heading detection).
    5. Chunks are indexed in TF-IDF retriever for the chatbot.

    Response: filename, file_id, text_length, chunks, topics, topic_list.
    """
    filename = file.filename or "upload.bin"
    if not pdf_processor.is_allowed_file(filename):
        raise HTTPException(400, "Only .pdf and .txt files are allowed.")

    # Save file to disk
    save_path = os.path.join(UPLOAD_DIR, filename)
    try:
        with open(save_path, "wb") as f_out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f_out.write(chunk)
    except Exception as exc:
        raise HTTPException(500, f"Could not save file: {exc}")

    # Extract text + chunk in a thread (CPU-bound)
    try:
        raw_text = await asyncio.to_thread(pdf_processor.extract_text, save_path)
        raw_text = pdf_processor.clean_text(raw_text)
        _, chunks = await asyncio.to_thread(pdf_processor.process_file, save_path)
    except RuntimeError as exc:
        raise HTTPException(500, str(exc))
    except Exception as exc:
        logger.error("Extraction failed: %s", exc)
        raise HTTPException(400, f"Could not read uploaded file: {exc}")

    # Guard: empty file
    if not raw_text.strip() or not chunks:
        raise HTTPException(
            400,
            "No readable text found. Please upload a text-based PDF or enable OCR."
        )

    # Extract topics offline (no AI / Ollama needed)
    topics = await asyncio.to_thread(extract_topics, raw_text, chunks)

    # Clear old session, populate with new data
    _reset_session()
    new_id = str(uuid.uuid4())[:8]
    ACTIVE_SESSION.update({
        "file_id":  new_id,
        "filename": filename,
        "raw_text": raw_text,
        "chunks":   chunks,
        "topics":   topics,
    })

    # Index in TF-IDF retriever (chatbot uses this)
    retriever.add_file(filename, chunks)

    # Debug logs (visible in server console during demo)
    logger.info("[Tutor] New upload | file_id=%s | file=%s | text=%d | chunks=%d | topics=%d",
                new_id, filename, len(raw_text), len(chunks), len(topics))
    print(f"[Tutor] ✅ New file uploaded | file_id={new_id}")
    print(f"[Tutor]    Filename       : {filename}")
    print(f"[Tutor]    Text length    : {len(raw_text)} chars")
    print(f"[Tutor]    Chunks created : {len(chunks)}")
    print(f"[Tutor]    Topics found   : {len(topics)}")

    # Award +10 points for uploading study material
    _award_points("upload_material", 10)

    return {
        "status":      "success",
        "file_id":     new_id,
        "filename":    filename,
        "text_length": len(raw_text),
        "chunks":      len(chunks),
        "topics":      len(topics),
        "topic_list":  [
            {"id": t["topic_id"], "title": t["title"], "difficulty": t["difficulty"]}
            for t in topics
        ],
        "ranking":  dict(ACTIVE_SESSION["ranking"]),
        "message": f"File uploaded and analysed. Found {len(topics)} topics.",
    }


# ---------------------------------------------------------------------------
# B. Save Student Learning Profile
# ---------------------------------------------------------------------------

class StudentProfile(BaseModel):
    learning_level: str   = "Medium"       # Beginner / Medium / Advanced
    daily_hours:    float = 2.0             # hours per day
    exam_date:      str   = ""             # YYYY-MM-DD
    light_days:     str   = "No light days" # Sunday / Saturday and Sunday / No light days
    target:         str   = "Score Good Marks"  # Pass / Score Good Marks / Top Score
    learning_style: str   = "Mixed"        # Theory first / Examples first / Quiz first / Mixed
    confidence:     int   = 3              # 1–5


@router.post("/save-profile")
async def save_profile(profile: StudentProfile = Body(...)):
    """
    Step 2 — Save the student's learning profile.
    Must be called after /upload.
    Stores answers in ACTIVE_SESSION["student_profile"].
    """
    if not ACTIVE_SESSION["file_id"]:
        raise HTTPException(400, "Please upload study material first.")

    ACTIVE_SESSION["student_profile"] = profile.model_dump()

    # Debug logs
    logger.info("[Tutor] Profile saved | level=%s | hours=%s | exam=%s | confidence=%s",
                profile.learning_level, profile.daily_hours,
                profile.exam_date, profile.confidence)
    print(f"[Tutor] Profile saved | daily_hours={profile.daily_hours} | exam_date={profile.exam_date}")
    print(f"[Tutor]   Level={profile.learning_level} | Target={profile.target} | Confidence={profile.confidence}")

    return {"status": "success", "message": "Learning profile saved."}


# ---------------------------------------------------------------------------
# C. Generate Study Plan
# ---------------------------------------------------------------------------

@router.post("/generate-plan")
async def generate_plan():
    """
    Step 3 — Generate a personalised calendar study plan.

    Requires file uploaded AND student profile saved.
    Uses ONLY ACTIVE_SESSION["topics"] (latest PDF) — never old data.
    Replaces any previously generated plan in ACTIVE_SESSION.
    """
    if not ACTIVE_SESSION["file_id"]:
        raise HTTPException(400, "Please upload study material first.")
    if not ACTIVE_SESSION["student_profile"]:
        raise HTTPException(400, "Please complete the learning profile first.")
    if not ACTIVE_SESSION["topics"]:
        raise HTTPException(400, "No topics found in the uploaded material.")

    topics  = ACTIVE_SESSION["topics"]
    profile = ACTIVE_SESSION["student_profile"]

    # Run the planner in a thread (pure Python, no I/O)
    plan = await asyncio.to_thread(generate_study_plan, topics, profile)

    # Replace old plan, reset completed task counter for new plan
    ACTIVE_SESSION["study_plan"] = plan
    ACTIVE_SESSION["progress"]["total_tasks"]     = len(plan)
    ACTIVE_SESSION["progress"]["completed_tasks"] = 0

    # Award +20 points for generating a study plan
    _award_points("generate_plan", 20)

    # Debug logs
    logger.info("[Tutor] Plan generated | file_id=%s | topics=%d | days=%d",
                ACTIVE_SESSION["file_id"], len(topics), len(plan))
    print(f"[Tutor] Plan generated | file_id={ACTIVE_SESSION['file_id']}")
    print(f"[Tutor]   Topics used={len(topics)} | Plan items={len(plan)} | Old plan replaced ✅")

    return {
        "status":   "success",
        "plan":     plan,
        "days":     len(plan),
        "ranking":  dict(ACTIVE_SESSION["ranking"]),
        "progress": dict(ACTIVE_SESSION["progress"]),
        "message":  f"Study plan generated: {len(plan)} days.",
    }


# ---------------------------------------------------------------------------
# D. Get Plan
# ---------------------------------------------------------------------------

@router.get("/get-plan")
async def get_plan():
    """Return the current calendar study plan."""
    return {
        "status":   "success",
        "file_id":  ACTIVE_SESSION["file_id"],
        "filename": ACTIVE_SESSION["filename"],
        "plan":     ACTIVE_SESSION["study_plan"],
    }


# ---------------------------------------------------------------------------
# E. Chat (always uses the latest uploaded file)
# ---------------------------------------------------------------------------

class TutorChatRequest(BaseModel):
    message: str
    mode:    Optional[str] = "normal"


@router.post("/chat")
async def tutor_chat(req: TutorChatRequest = Body(...)):
    """
    Chat using ACTIVE_SESSION chunks — the latest uploaded file only.

    - General questions (summarize, main topic, etc.) → first-N chunks + top-2 TF-IDF.
    - Specific questions → TF-IDF retrieval with similarity threshold.
    - Saves Q&A in ACTIVE_SESSION["chat_history"].
    """
    question = (req.message or "").strip()
    if not question:
        raise HTTPException(400, "Question is required.")

    # Guard: no file uploaded
    if not ACTIVE_SESSION["file_id"] or not ACTIVE_SESSION["chunks"]:
        return {"response": ai_tutor.NO_FILE_MESSAGE, "sources": []}

    mode = req.mode or "normal"

    # Smart context: general vs specific detection
    top_chunks, top_sources, best_sim, is_general = retriever.get_context_for_question(
        question, mode=mode, top_k=5
    )

    # Debug logs
    logger.info("[Chat] file_id=%s | filename=%s | chunks=%d | type=%s | sim=%.3f | mode=%s",
                ACTIVE_SESSION["file_id"], ACTIVE_SESSION["filename"],
                len(top_chunks), "GENERAL" if is_general else "SPECIFIC",
                best_sim, mode)
    print(f"[Chat] file_id={ACTIVE_SESSION['file_id']} | filename={ACTIVE_SESSION['filename']}")
    print(f"[Chat]   chunks_used={len(top_chunks)} | type={'GENERAL' if is_general else 'SPECIFIC'}")
    print(f"[Chat]   similarity={best_sim:.3f} | mode={mode}")

    if not top_chunks:
        return {"response": ai_tutor.NO_FILE_MESSAGE, "sources": []}

    # Similarity threshold guard for specific questions only
    if not is_general and best_sim < retriever.SIMILARITY_THRESHOLD:
        return {"response": ai_tutor.NOT_IN_MATERIAL_MESSAGE, "sources": []}

    prompt = ai_tutor.build_prompt(top_chunks, question, mode)
    answer_text, unavailable_msg = await asyncio.to_thread(ai_tutor.generate_answer, prompt)

    if not answer_text:
        return {"response": unavailable_msg, "sources": []}

    # Validate answer stays in context
    is_valid, reason = ai_tutor.validate_answer(answer_text, top_chunks, is_general=is_general)
    if not is_valid:
        logger.info("[Chat] Rejected by validator: %s", reason)
        return {"response": ai_tutor.NOT_IN_MATERIAL_MESSAGE, "sources": []}

    # Save to session history
    ACTIVE_SESSION["chat_history"].append({"question": question, "answer": answer_text})

    # Award +2 points for engaging with the AI tutor
    _award_points("ask_ai_tutor", 2)

    seen: set = set()
    sources = []
    for s in top_sources:
        if s not in seen:
            seen.add(s)
            sources.append({"title": s, "score": round(best_sim, 3)})

    return {"response": answer_text, "sources": sources, "ranking": dict(ACTIVE_SESSION["ranking"])}


# ---------------------------------------------------------------------------
# F. Clear
# ---------------------------------------------------------------------------

@router.post("/clear")
async def tutor_clear():
    """Clear everything: file, chunks, topics, plan, chat history."""
    _reset_session()
    # Best-effort disk cleanup
    try:
        for fname in os.listdir(UPLOAD_DIR):
            fp = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(fp):
                os.remove(fp)
    except Exception as exc:
        logger.warning("Disk cleanup partial error: %s", exc)
    print("[Tutor] Session cleared by user — ready for new upload.")
    return {"status": "success", "message": "Session cleared. Ready for new upload."}


# ---------------------------------------------------------------------------
# G. Status
# ---------------------------------------------------------------------------

@router.get("/status")
async def tutor_status():
    """Return a full snapshot of the current active session for debugging and UI restore."""
    return {
        "has_file":        bool(ACTIVE_SESSION["file_id"]),
        "file_id":         ACTIVE_SESSION["file_id"],
        "filename":        ACTIVE_SESSION["filename"],
        "chunks":          len(ACTIVE_SESSION["chunks"]),
        "topics":          len(ACTIVE_SESSION["topics"]),
        "has_profile":     bool(ACTIVE_SESSION["student_profile"]),
        "plan_items":      len(ACTIVE_SESSION["study_plan"]),
        "chat_messages":   len(ACTIVE_SESSION["chat_history"]),
        "has_mock_test":   bool(ACTIVE_SESSION["mock_test"]),
        "mock_questions":  len(ACTIVE_SESSION["mock_test"]),
        "has_mock_result": bool(ACTIVE_SESSION["mock_test_result"]),
        "ranking":         dict(ACTIVE_SESSION["ranking"]),
        "progress":        dict(ACTIVE_SESSION["progress"]),
        "attendance_days": len(ACTIVE_SESSION["attendance"]),
        "profile":         dict(ACTIVE_SESSION["profile"]),
    }


# ---------------------------------------------------------------------------
# H. Complete a Calendar Task
# ---------------------------------------------------------------------------

class CompleteTaskRequest(BaseModel):
    event_id: str   # matches the "id" field in the plan event dict

@router.post("/complete-task")
async def complete_task(req: CompleteTaskRequest = Body(...)):
    """
    Mark a study plan task as completed.
    - Updates the completed flag on the event.
    - Increments progress.completed_tasks.
    - Awards +15 ranking points.
    """
    plan = ACTIVE_SESSION["study_plan"]
    found = False
    for event in plan:
        if event.get("id") == req.event_id:
            if event.get("completed"):
                return {"status": "already_done", "message": "Task already completed."}
            event["completed"] = True
            found = True
            break

    if not found:
        raise HTTPException(404, f"Event '{req.event_id}' not found in current plan.")

    ACTIVE_SESSION["progress"]["completed_tasks"] += 1
    ranking = _award_points("complete_task", 15)

    logger.info("[Task] Completed event_id=%s | completed=%d/%d",
                req.event_id,
                ACTIVE_SESSION["progress"]["completed_tasks"],
                ACTIVE_SESSION["progress"]["total_tasks"])
    print(f"[Task] ✅ {req.event_id} completed | {ACTIVE_SESSION['progress']['completed_tasks']}/{ACTIVE_SESSION['progress']['total_tasks']}")

    return {
        "status":   "success",
        "message":  "Task marked as completed!",
        "progress": dict(ACTIVE_SESSION["progress"]),
        "ranking":  ranking,
    }


# ---------------------------------------------------------------------------
# I. Attendance
# ---------------------------------------------------------------------------

@router.post("/mark-attendance")
async def mark_attendance():
    """
    Mark today's attendance as Present.
    - Idempotent: returns a warning if already marked today.
    - Awards +10 ranking points.
    - Updates study streak.
    """
    from datetime import date as _date, datetime as _dt
    today     = _date.today().isoformat()        # "YYYY-MM-DD"
    now_time  = _dt.now().strftime("%H:%M")

    attendance = ACTIVE_SESSION["attendance"]

    if today in attendance:
        pct = _attendance_pct()
        logger.info("[Attendance] Already marked today=%s | pct=%.1f%%", today, pct)
        print(f"[Attendance] Already marked for {today}")
        return {
            "status":  "already_marked",
            "message": f"Attendance already marked for today ({today}).",
            "attendance_percentage": pct,
            "today_marked": True,
        }

    attendance[today] = {"status": "Present", "timestamp": now_time}

    # Update streak
    prog = ACTIVE_SESSION["progress"]
    prog["study_streak"] = prog.get("study_streak", 0) + 1

    pct = _attendance_pct()
    ranking = _award_points("mark_attendance", 10)

    logger.info("[Attendance] Marked Present | date=%s | time=%s | pct=%.1f%%", today, now_time, pct)
    print(f"[Attendance] ✅ Present | date={today} | pct={pct:.1f}%")

    return {
        "status":               "success",
        "message":              "Attendance marked for today!",
        "today_marked":         True,
        "attendance_percentage": pct,
        "streak":               prog["study_streak"],
        "ranking":              ranking,
    }


def _attendance_pct() -> float:
    """Calculate attendance percentage based on all recorded days."""
    att = ACTIVE_SESSION["attendance"]
    if not att: return 0.0
    present = sum(1 for v in att.values() if v.get("status") == "Present")
    return round(present / max(1, len(att)) * 100, 1)


@router.get("/attendance-status")
async def attendance_status():
    """Return today's status, attendance percentage, and recent history (last 14 days)."""
    from datetime import date as _date
    today = _date.today().isoformat()
    att   = ACTIVE_SESSION["attendance"]
    # Last 14 entries sorted descending
    history = [
        {"date": d, **v}
        for d, v in sorted(att.items(), reverse=True)
    ][:14]

    pct = _attendance_pct()
    logger.info("[Attendance] Status requested | today_marked=%s | pct=%.1f%%",
                today in att, pct)
    print(f"[Attendance] Status | today_marked={today in att} | pct={pct}%")

    return {
        "today_marked":          today in att,
        "attendance_percentage": pct,
        "total_days":            len(att),
        "present_days":          sum(1 for v in att.values() if v.get("status") == "Present"),
        "streak":                ACTIVE_SESSION["progress"].get("study_streak", 0),
        "history":               history,
    }


# ---------------------------------------------------------------------------
# J. Ranking
# ---------------------------------------------------------------------------

@router.get("/ranking")
async def get_ranking():
    """Return the current ranking / gamification state."""
    r   = ACTIVE_SESSION["ranking"]
    pro = ACTIVE_SESSION["progress"]
    logger.info("[Ranking] Fetched | points=%d | rank=%s | badge=%s",
                r["points"], r["rank"], r["badge"])
    return {
        "status":  "success",
        "ranking": dict(r),
        "progress": dict(pro),
    }

@router.post("/update-ranking")
async def update_ranking(action: str = Body(..., embed=True),
                         points: int = Body(0,   embed=True)):
    """
    Manual ranking update endpoint.
    Useful for external triggers (quiz completion, etc.).
    """
    ranking = _award_points(action, points)
    return {"status": "success", "ranking": ranking}


# ---------------------------------------------------------------------------
# K. Profile
# ---------------------------------------------------------------------------

@router.get("/profile")
async def get_profile():
    """Return the student profile details stored in ACTIVE_SESSION."""
    p = ACTIVE_SESSION["profile"]
    # Log which fields are missing
    missing = [k for k, v in p.items() if not str(v).strip()]
    logger.info("[Profile] Fetched | missing_fields=%s", missing or "none")
    print(f"[Profile] Fetched | missing={missing or 'none'}")
    return {"status": "success", "profile": dict(p)}


class ProfileData(BaseModel):
    full_name:          str   = ""
    email:              str   = ""
    phone:              str   = ""
    class_or_semester:  str   = ""
    department:         str   = ""
    college:            str   = ""
    preferred_language: str   = "English"
    learning_goal:      str   = ""
    daily_study_hours:  float = 2.0
    exam_target:        str   = ""


@router.post("/update-profile")
async def update_profile(data: ProfileData = Body(...)):
    """Save/update the student profile details in ACTIVE_SESSION."""
    ACTIVE_SESSION["profile"].update(data.model_dump())
    p = ACTIVE_SESSION["profile"]
    logger.info("[Profile] Updated | name=%s | email=%s | college=%s",
                p.get("full_name"), p.get("email"), p.get("college"))
    print(f"[Profile] Updated | name={p.get('full_name')} | college={p.get('college')}")
    return {"status": "success", "profile": dict(p), "message": "Profile updated successfully."}



# ---------------------------------------------------------------------------
# L. Mock Test — Generate
# ---------------------------------------------------------------------------

@router.post("/generate-mock-test")
async def generate_mock_test():
    """
    Generate 10 MCQ questions from the LATEST uploaded file only.

    Flow:
    1. Check that a file has been uploaded (ACTIVE_SESSION["chunks"]).
    2. Call generate_mock_test_from_context (tries Ollama, falls back).
    3. Store questions in ACTIVE_SESSION["mock_test"].
    4. Award +5 ranking points for generating a test.

    Returns the list of questions (without correct_answer, for fair testing).
    """
    if not ACTIVE_SESSION["file_id"] or not ACTIVE_SESSION["chunks"]:
        raise HTTPException(400, "Please upload study material first.")

    chunks = ACTIVE_SESSION["chunks"]
    topics = ACTIVE_SESSION["topics"]

    logger.info("[MockTest] Generating | file_id=%s | chunks=%d | topics=%d",
                ACTIVE_SESSION["file_id"], len(chunks), len(topics))
    print(f"[MockTest] Generating | file_id={ACTIVE_SESSION['file_id']} | file={ACTIVE_SESSION['filename']}")

    # Run in a thread — Ollama call can block
    questions = await asyncio.to_thread(
        generate_mock_test_from_context, chunks, topics
    )

    if not questions:
        raise HTTPException(500, "Could not generate questions from the uploaded material. "
                                 "Please ensure Ollama is running or the file has sufficient content.")

    # Store with correct answers for grading; return without correct_answer to client
    ACTIVE_SESSION["mock_test"]        = questions
    ACTIVE_SESSION["mock_test_result"] = {}   # clear old result

    # Award points for generating a test
    _award_points("generate_mock_test", 5)

    logger.info("[MockTest] Generated %d questions | file=%s", len(questions), ACTIVE_SESSION["filename"])
    print(f"[MockTest] ✅ {len(questions)} questions generated from {ACTIVE_SESSION['filename']}")

    # Return questions WITHOUT correct_answer so the UI can show them fairly
    safe_questions = [
        {k: v for k, v in q.items() if k != "correct_answer"}
        for q in questions
    ]
    return {
        "status":    "success",
        "filename":  ACTIVE_SESSION["filename"],
        "questions": safe_questions,
        "total":     len(safe_questions),
        "message":   f"Generated {len(safe_questions)} questions from {ACTIVE_SESSION['filename']}.",
    }


# ---------------------------------------------------------------------------
# M. Mock Test — Get (returns questions without answers for display)
# ---------------------------------------------------------------------------

@router.get("/get-mock-test")
async def get_mock_test():
    """Return the currently stored mock test questions (without correct answers)."""
    if not ACTIVE_SESSION["mock_test"]:
        return {
            "status":    "no_test",
            "questions": [],
            "filename":  ACTIVE_SESSION.get("filename"),
            "message":   "No mock test generated yet.",
        }
    safe_questions = [
        {k: v for k, v in q.items() if k != "correct_answer"}
        for q in ACTIVE_SESSION["mock_test"]
    ]
    return {
        "status":    "success",
        "filename":  ACTIVE_SESSION["filename"],
        "questions": safe_questions,
        "total":     len(safe_questions),
    }


# ---------------------------------------------------------------------------
# N. Mock Test — Submit and Grade
# ---------------------------------------------------------------------------

class MockSubmitRequest(BaseModel):
    answers: Dict[str, str]   # {"q1": "A", "q2": "C", ...}


@router.post("/submit-mock-test")
async def submit_mock_test(req: MockSubmitRequest = Body(...)):
    """
    Grade the student's mock test answers.

    Logic:
    - Compare student answers with ACTIVE_SESSION["mock_test"] correct_answers.
    - Calculate score and percentage.
    - Identify weak topics (topics of wrong answers).
    - Save result in ACTIVE_SESSION["mock_test_result"].
    - Award ranking points: >=8 correct → +40, 5-7 → +25, <5 → +10.

    Returns: score, total, percentage, weak_topics, review list.
    """
    questions = ACTIVE_SESSION["mock_test"]
    if not questions:
        raise HTTPException(400, "No mock test found. Please generate a test first.")

    answers      = req.answers
    score        = 0
    review       = []
    weak_topics:  set = set()

    for q in questions:
        qid      = q.get("id", "")
        selected = answers.get(qid, "").upper().strip()
        correct  = (q.get("correct_answer") or "").upper().strip()
        is_right = selected == correct

        if is_right:
            score += 1
        else:
            weak_topics.add(q.get("topic", "General"))

        review.append({
            "id":             qid,
            "question":       q.get("question", ""),
            "selected":       selected,
            "correct_answer": correct,
            "is_correct":     is_right,
            "explanation":    q.get("explanation", ""),
            "topic":          q.get("topic", "General"),
        })

    total      = len(questions)
    percentage = round(score / max(1, total) * 100, 1)
    weak_list  = sorted(weak_topics)

    # Save result
    result = {
        "score":       score,
        "total":       total,
        "percentage":  percentage,
        "weak_topics": weak_list,
        "review":      review,
    }
    ACTIVE_SESSION["mock_test_result"] = result
    ACTIVE_SESSION["progress"]["mock_score"] = score

    # Award ranking points based on performance
    pts_map = {score >= 8: 40, score >= 5: 25}
    pts     = next((v for k, v in pts_map.items() if k), 10)
    _award_points("mock_test_submit", pts)

    logger.info("[MockTest] Submitted | score=%d/%d | pct=%.1f%% | weak=%s | pts=+%d",
                score, total, percentage, weak_list, pts)
    print(f"[MockTest] ✅ Score={score}/{total} ({percentage}%) | weak_topics={weak_list} | +{pts} pts")

    return {
        "status":     "success",
        "score":      score,
        "total":      total,
        "percentage": percentage,
        "weak_topics": weak_list,
        "review":     review,
        "ranking":    dict(ACTIVE_SESSION["ranking"]),
        "progress":   dict(ACTIVE_SESSION["progress"]),
        "suggestion": (
            f"Revise these weak topics: {', '.join(weak_list)}. "
            "Use the AI Tutor or update your Planner for revision."
            if weak_list else
            "Excellent! All topics covered. Keep up the great work!"
        ),
    }


# ---------------------------------------------------------------------------
# O. Update Plan from Mock Test (add weak-topic revision events)
# ---------------------------------------------------------------------------

@router.post("/update-plan-from-test")
async def update_plan_from_test():
    """
    After a mock test, add revision events for weak topics into the study plan.

    Logic:
    - Read weak_topics from ACTIVE_SESSION["mock_test_result"].
    - Find the next available date after the last plan event.
    - Add one "Weak Topic Revision" event per weak topic.
    - Avoid duplicating existing revision events for the same topic.
    - Update ACTIVE_SESSION["progress"]["total_tasks"].

    Returns the updated plan.
    """
    result = ACTIVE_SESSION.get("mock_test_result", {})
    if not result:
        raise HTTPException(400, "No mock test result found. Submit a test first.")

    weak_topics = result.get("weak_topics", [])
    if not weak_topics:
        return {
            "status":  "no_change",
            "message": "No weak topics found. Your plan is already optimal!",
            "plan":    ACTIVE_SESSION["study_plan"],
        }

    plan = ACTIVE_SESSION["study_plan"]

    # Find the next date to insert revision events
    from datetime import date as _date, timedelta
    if plan:
        last_date_str = max(e["date"] for e in plan)
        next_date     = _date.fromisoformat(last_date_str) + timedelta(days=1)
    else:
        next_date = _date.today()

    # Existing revision topics (avoid duplicates)
    existing_revisions = {
        e["title"]
        for e in plan
        if e.get("task_type") == "Weak Topic Revision"
    }

    added = 0
    for topic in weak_topics:
        title = f"Weak Topic Revision: {topic}"
        if title in existing_revisions:
            continue

        event_id = f"rev_{len(plan) + added + 1}"
        plan.append({
            "id":           event_id,
            "date":         next_date.isoformat(),
            "title":        title,
            "description":  f"Revisit '{topic}' — identified as weak from your mock test. "
                            "Ask the AI Tutor for a simple explanation.",
            "topics":       [topic],
            "duration_hours": 1.0,
            "task_type":    "Weak Topic Revision",
            "difficulty":   "Medium",
            "completed":    False,
            "colour":       "#dc2626",   # red — urgent revision
        })
        next_date += timedelta(days=1)
        added     += 1

    ACTIVE_SESSION["progress"]["total_tasks"] = len(plan)

    logger.info("[Plan] Weak-topic revision added | %d events | topics=%s", added, weak_topics)
    print(f"[Plan] ✅ Added {added} weak-topic revision events after mock test")

    return {
        "status":  "success",
        "added":   added,
        "topics":  weak_topics,
        "plan":    plan,
        "message": f"Added {added} revision event(s) for: {', '.join(weak_topics)}.",
    }
