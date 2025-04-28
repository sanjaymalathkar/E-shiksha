from fastapi import APIRouter, HTTPException, Request, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import os
import json
import logging
from datetime import datetime, timedelta
from app.core.ollama_local import run_ollama_json

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/planner",
    tags=["study_plan"],
    responses={404: {"description": "Not found"}},
)

# Models
class StudyPlanRequest(BaseModel):
    topics: Optional[List[str]] = None
    topics_per_day: int
    dlc_score: int  # Daily Learning Capacity Score (IQ level)
    analysis: Optional[str] = None
    exam_type: Optional[str] = None
    exam_date: Optional[str] = None

class StudyPlanResponse(BaseModel):
    status: str
    message: str
    plan: Optional[Dict[str, Any]] = None

@router.post("/create-study-plan", response_model=StudyPlanResponse)
async def create_study_plan(
    request: Request,
    plan_request: StudyPlanRequest = Body(...),
):
    """
    Generate a personalized study plan based on the student's mock test performance (IQ level).
    This endpoint should only be called after the student has completed the mock test.
    """
    try:
        # Validate the request
        if plan_request.dlc_score < 1 or plan_request.dlc_score > 10:
            raise HTTPException(status_code=400, detail="Daily Learning Capacity Score must be between 1 and 10")
        
        if plan_request.topics_per_day < 1:
            raise HTTPException(status_code=400, detail="Topics per day must be at least 1")
        
        # Generate the study plan using Ollama
        plan = await generate_study_plan_with_ollama(plan_request)
        
        # Save the study plan
        saved_plan = save_study_plan(plan)
        
        return StudyPlanResponse(
            status="success",
            message="Study plan generated successfully based on your IQ level",
            plan=saved_plan
        )
    except Exception as e:
        logger.error(f"Error generating study plan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def generate_study_plan_with_ollama(plan_request: StudyPlanRequest) -> Dict[str, Any]:
    """
    Generate a personalized study plan using Ollama based on the student's IQ level.
    
    Args:
        plan_request: The study plan request containing IQ level and other parameters
        
    Returns:
        Dictionary containing the study plan
    """
    # Prepare the prompt for Ollama
    topics_str = ", ".join(plan_request.topics) if plan_request.topics else "general topics"
    
    prompt = f"""
    Generate a personalized daily study plan for a student based on their mock test performance.
    
    Student's Learning Profile:
    - Daily Learning Capacity Score (IQ level): {plan_request.dlc_score}/10
    - Recommended topics per day: {plan_request.topics_per_day}
    - Topics to focus on: {topics_str}
    - Exam type: {plan_request.exam_type or 'General'}
    
    Analysis of student's performance:
    {plan_request.analysis or 'The student has completed a mock test that assessed their logical reasoning, problem-solving, comprehension, and memory recall abilities.'}
    
    Create a structured study plan with the following:
    
    1. A 14-day study schedule
    2. For each day, include:
       - {plan_request.topics_per_day} topics to study (based on their learning capacity)
       - 2-3 specific study activities for each topic
       - A study tip tailored to their learning capacity
    
    The difficulty and complexity of the topics should match their Daily Learning Capacity Score:
    - For scores 1-3: Focus on foundational concepts with simple explanations
    - For scores 4-6: Include moderate complexity with some connections between topics
    - For scores 7-10: Include advanced concepts and encourage deeper exploration
    
    Format the response as a JSON object with these keys:
    - metadata: Information about the plan (dlc_score, topics_per_day, exam_type, etc.)
    - days: Array of daily plans, each with topics, activities, and a tip
    
    Make sure the plan is realistic, encouraging, and tailored to the student's demonstrated abilities.
    """
    
    try:
        # Generate the study plan using Ollama
        result = run_ollama_json(prompt, model="llama3")
        
        # Validate the response
        if not isinstance(result, dict):
            raise ValueError("Invalid response format from Ollama")
        
        # Ensure the plan has the required structure
        if "days" not in result:
            result["days"] = []
        
        # Add metadata if not present
        if "metadata" not in result:
            result["metadata"] = {
                "dlc_score": plan_request.dlc_score,
                "topics_per_day": plan_request.topics_per_day,
                "exam_type": plan_request.exam_type,
                "exam_date": plan_request.exam_date,
                "generated_at": datetime.now().isoformat()
            }
        
        return result
    except Exception as e:
        logger.error(f"Error generating study plan with Ollama: {str(e)}")
        
        # Fallback to a template-based plan if Ollama fails
        return generate_fallback_study_plan(plan_request)

def generate_fallback_study_plan(plan_request: StudyPlanRequest) -> Dict[str, Any]:
    """
    Generate a fallback study plan if Ollama fails.
    
    Args:
        plan_request: The study plan request
        
    Returns:
        Dictionary containing the study plan
    """
    # Create a basic template for the study plan
    plan = {
        "metadata": {
            "dlc_score": plan_request.dlc_score,
            "topics_per_day": plan_request.topics_per_day,
            "exam_type": plan_request.exam_type,
            "exam_date": plan_request.exam_date,
            "generated_at": datetime.now().isoformat()
        },
        "days": []
    }
    
    # Define some generic topics if none are provided
    default_topics = [
        "Basic Concepts", "Fundamentals", "Core Principles",
        "Key Theories", "Essential Methods", "Primary Techniques",
        "Foundational Knowledge", "Main Ideas", "Critical Concepts",
        "Important Formulas", "Key Definitions", "Standard Procedures",
        "Common Applications", "Practical Examples", "Case Studies"
    ]
    
    topics_to_use = plan_request.topics if plan_request.topics else default_topics
    
    # Generate 14 days of study plan
    for day in range(1, 15):
        # Select topics for the day
        day_topics = []
        for i in range(min(plan_request.topics_per_day, len(topics_to_use))):
            topic_index = (day + i) % len(topics_to_use)
            day_topics.append(topics_to_use[topic_index])
        
        # Create activities based on IQ level
        activities = []
        if plan_request.dlc_score <= 3:
            activities = [
                f"Read and summarize the main points about {day_topics[0]}",
                f"Create flashcards for key terms in {day_topics[0]}",
                "Take a 5-minute break after every 25 minutes of study"
            ]
        elif plan_request.dlc_score <= 6:
            activities = [
                f"Study and take notes on {day_topics[0]}",
                f"Practice example problems related to {day_topics[0]}",
                "Review yesterday's material for 15 minutes"
            ]
        else:
            activities = [
                f"Deep dive into advanced concepts of {day_topics[0]}",
                f"Solve complex problems involving multiple aspects of {day_topics[0]}",
                "Connect today's topics with previously learned material"
            ]
        
        # Create a study tip based on IQ level
        tip = ""
        if plan_request.dlc_score <= 3:
            tip = "Break down complex topics into smaller, manageable parts. Focus on understanding one concept at a time."
        elif plan_request.dlc_score <= 6:
            tip = "Try teaching the material to someone else or explaining it out loud to reinforce your understanding."
        else:
            tip = "Challenge yourself by finding connections between different topics and exploring advanced applications."
        
        # Add the day to the plan
        plan["days"].append({
            "day": day,
            "topics": day_topics,
            "activities": activities,
            "tip": tip
        })
    
    return plan

def save_study_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Save the study plan to a file.
    
    Args:
        plan: The study plan to save
        
    Returns:
        The saved study plan
    """
    try:
        # Create the output directory if it doesn't exist
        output_dir = os.path.join("data", "output")
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate a filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"study_plan_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)
        
        # Save the plan to a file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)
        
        # Add file information to the plan
        plan["file_info"] = {
            "filename": filename,
            "path": filepath,
            "created_at": datetime.now().isoformat()
        }
        
        return plan
    except Exception as e:
        logger.error(f"Error saving study plan: {str(e)}")
        # Return the original plan if saving fails
        return plan
