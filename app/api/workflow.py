import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from typing import List, Any, Dict
from app.core.ollama_local import run_ollama_json
import httpx

router = APIRouter(
    prefix="/api/workflow",
    tags=["workflow"],
)

@router.post("/start")
async def workflow_start(
    files: List[UploadFile] = File(...)
) -> Dict[str, Any]:
    """
    Step 1: Upload and analyze resource. Immediately process files locally with Ollama to extract topics and key info.
    Then trigger a general knowledge quiz.
    """
    # Read and combine text from all uploaded files
    combined_text = []
    for file in files:
        content = await file.read()
        try:
            text = content.decode('utf-8')
        except:
            text = ''
        combined_text.append(text)
    resource_text = "\n".join(combined_text)

    # Analyze resource with Ollama
    analysis_prompt = (
        f"Extract the key information, topics, and learning material from the following resource text:\n{resource_text}\n"
        "Return a JSON object with keys: topics (list of strings), key_info (string), learning_material (list of strings)."
    )
    analysis = run_ollama_json(analysis_prompt)
    topics = analysis.get('topics') if isinstance(analysis, dict) else []
    if not isinstance(topics, list):
        topics = []

    # Generate a general knowledge quiz
    quiz_prompt = (
        "Generate a quiz of 10 questions covering MCQs, short-answer, and logical reasoning puzzles. "
        "Return a JSON array of objects with fields: id, type (mcq/short/puzzle), difficulty, question, options (if mcq)."
    )
    quiz = run_ollama_json(quiz_prompt)
    if not isinstance(quiz, list):
        quiz = []

    return {
        "status": "success",
        "message": "Resource analyzed and quiz generated.",
        "topics": topics,
        "quiz": quiz
    }

@router.post("/notify")
async def workflow_notify(
    email: str = Body(...),
    plan: Any = Body(...)
) -> Dict[str, Any]:
    """
    Send the daily learning plan via SparkPost email.
    Requires SPARKPOST_API_KEY in environment.
    """
    api_key = os.getenv('SPARKPOST_API_KEY')
    if not api_key:
        raise HTTPException(status_code=400, detail="SPARKPOST_API_KEY not set")
    data = {
        "options": {"sandbox": True},
        "content": {
            "from": "sandbox@sparkpostmail.com",
            "subject": "Your Daily Learning Plan",
            "html": f"<pre>{plan}</pre>",
            "text": str(plan)
        },
        "recipients": [{"address": email}]
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.sparkpost.com/api/v1/transmissions",
            json=data,
            headers={"Authorization": api_key}
        )
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return {"status": "sent", "detail": resp.json()}

@router.post("/submit-quiz")
async def workflow_submit_quiz(
    payload: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """
    Step 3: Evaluate quiz answers and assign topics based on IQ level.
    """
    topics = payload.get('topics', [])
    answers = payload.get('answers', {})
    # Use Ollama to evaluate IQ performance
    eval_prompt = (
        f"Evaluate the following quiz answers and compute a score and daily learning capacity score (1-10)."
        f" Return JSON with keys: score, daily_learning_capacity, recommended_topics_per_day. Answers: {answers}"
    )
    result = run_ollama_json(eval_prompt)
    # Fallback to simple scoring if LLM fails
    score = int(result.get('score', 0))
    dlc = int(result.get('daily_learning_capacity', 1))
    rec = int(result.get('recommended_topics_per_day', 1))
    # Assign topics based on dlc
    if dlc >= 7:
        assigned = topics[-rec:] if len(topics) >= rec else topics
    else:
        assigned = topics[:rec] if len(topics) >= rec else topics
    return {
        'score': score,
        'daily_learning_capacity': dlc,
        'assigned_topics': assigned
    }

@router.post("/feedback")
async def workflow_feedback(
    feedback: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """
    Step 4: Receive user feedback to refine future suggestions.
    """
    # For now, simply acknowledge feedback
    return {
        'status': 'received',
        'feedback': feedback
    }
