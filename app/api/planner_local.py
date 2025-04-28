from fastapi import APIRouter, HTTPException, Request, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.core.ollama_local import run_ollama_json

router = APIRouter(
    prefix="/api/planner",
    tags=["planner-local"],
    responses={404: {"description": "Not found"}},
)

class LocalPlannerRequest(BaseModel):
    exam_type: Optional[str] = None
    exam_date: Optional[str] = None
    topics: Optional[List[str]] = None
    topics_per_day: int
    dlc_score: int
    analysis: Optional[str] = None

class LocalPlannerResponse(BaseModel):
    status: str
    message: str
    plan: Any

@router.post("/create-study-plan", response_model=LocalPlannerResponse)
async def create_study_plan(request: Request, planner_request: LocalPlannerRequest = Body(...)):
    """
    Generate a personalized daily study plan using Ollama locally, based on the student's mock test performance.
    """
    prompt = (
        f"Generate a personalized daily study plan for a student. "
        f"Exam type: {planner_request.exam_type or 'General'}. "
        f"Exam date: {planner_request.exam_date or 'Not specified'}. "
        f"Topics: {', '.join(planner_request.topics or [])}. "
        f"The student can handle {planner_request.topics_per_day} topics per day, based on a daily learning capacity score of {planner_request.dlc_score} (1-10). "
        f"Provide a day-wise breakdown of topics to study, with a short motivational tip for each day. Format as JSON."
    )
    plan = run_ollama_json(prompt, model="llama3")
    return LocalPlannerResponse(
        status="success",
        message="Personalized study plan created successfully.",
        plan=plan
    )
