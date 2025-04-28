import os
import json
import logging
from fastapi import APIRouter, HTTPException, Request, Body
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.core.ollama_local import run_ollama_json
from app.core.email import email_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/study-plan",
    tags=["study-plan"],
    responses={404: {"description": "Not found"}},
)

# Models
class StudyPlanRequest(BaseModel):
    assessment_id: str
    email: Optional[EmailStr] = None
    send_email: bool = False

class StudyPlanResponse(BaseModel):
    status: str
    message: str
    plan_id: str
    plan: Dict[str, Any]
    email_sent: bool = False

class StudyPlanFeedback(BaseModel):
    plan_id: str
    feedback: str
    rating: int  # 1-5 scale
    too_difficult: bool = False
    too_easy: bool = False
    comments: Optional[str] = None

class FeedbackResponse(BaseModel):
    status: str
    message: str
    updated_plan: Optional[Dict[str, Any]] = None

@router.post("/generate", response_model=StudyPlanResponse)
async def generate_study_plan(
    request: Request,
    plan_request: StudyPlanRequest = Body(...),
):
    """
    Generate a personalized study plan based on the user's IQ assessment.
    The plan includes topics assigned based on the user's learning capacity.
    """
    try:
        # Get the assessment result
        assessment_file = os.path.join("data", "assessments", f"{plan_request.assessment_id}_result.json")
        if not os.path.exists(assessment_file):
            raise HTTPException(status_code=404, detail="Assessment result not found")

        with open(assessment_file, "r", encoding="utf-8") as f:
            assessment = json.load(f)

        # Get the resource
        resource_id = assessment.get("resource_id")
        resource_file = os.path.join("data", "resources", resource_id, "analysis.json")

        resource_content = ""
        resource_topics = assessment.get("recommended_topics", [])

        if os.path.exists(resource_file):
            with open(resource_file, "r", encoding="utf-8") as f:
                resource = json.load(f)
                resource_content = resource.get("full_text", "")
                if not resource_topics:
                    resource_topics = [{"topic": t, "difficulty": "mixed"} for t in resource.get("topics", [])]

        # Generate a personalized study plan using Ollama
        topics_str = ", ".join([t["topic"] for t in resource_topics])
        learning_capacity = assessment.get("learning_capacity", 5)
        topics_per_day = assessment.get("topics_per_day", 3)

        prompt = f"""
        Generate a personalized daily study plan for a student based on their IQ assessment.

        Student's Learning Profile:
        - IQ Score: {assessment.get("iq_score", 100)}
        - Learning Capacity: {learning_capacity}/10
        - Topics Per Day: {topics_per_day}
        - Strengths: {', '.join(assessment.get("strengths", []))}
        - Weaknesses: {', '.join(assessment.get("weaknesses", []))}

        Topics to include in the study plan:
        {topics_str}

        Create a structured 14-day study plan with:
        1. For each day, include {topics_per_day} topics to study
        2. For each topic, provide:
           - Specific learning objectives
           - Recommended study activities
           - Estimated time needed (in minutes)
           - Resources to use
        3. Include a daily study tip tailored to the student's learning capacity
        4. Ensure the difficulty of topics matches the student's learning capacity:
           - For capacity 1-3: Focus on foundational concepts with simple explanations
           - For capacity 4-6: Include moderate complexity with some connections between topics
           - For capacity 7-10: Include advanced concepts and encourage deeper exploration

        Format the response as a JSON object with these keys:
        - metadata: Information about the plan (learning_capacity, topics_per_day, etc.)
        - days: Array of daily plans, each with date, topics, activities, and a tip

        Make the plan realistic, encouraging, and tailored to the student's demonstrated abilities.

        IMPORTANT: Your response must be a valid JSON object that can be parsed directly. Do not include any explanatory text before or after the JSON.
        """

        try:
            # Generate the study plan using Ollama
            plan_result = run_ollama_json(prompt, model="llama3")

            # Validate the response
            if not isinstance(plan_result, dict):
                raise ValueError("Invalid response format from Ollama")

            # Ensure the plan has the required structure
            if "days" not in plan_result:
                plan_result["days"] = []

            # Add metadata if not present
            if "metadata" not in plan_result:
                plan_result["metadata"] = {
                    "learning_capacity": learning_capacity,
                    "topics_per_day": topics_per_day,
                    "iq_score": assessment.get("iq_score", 100),
                    "strengths": assessment.get("strengths", []),
                    "weaknesses": assessment.get("weaknesses", []),
                    "generated_at": datetime.now().isoformat()
                }

            # Add dates to days if not present
            for i, day in enumerate(plan_result["days"]):
                if "date" not in day:
                    # Use simple day numbers instead of actual dates
                    day["date"] = f"Day {i+1}"

        except Exception as e:
            logger.error(f"Error generating study plan with Ollama: {str(e)}")

            # Fallback to a template-based plan
            plan_result = generate_fallback_study_plan(assessment, resource_topics)

        # Generate a unique plan ID
        plan_id = f"plan_{os.urandom(4).hex()}"

        # Save the study plan
        plans_folder = os.path.join("data", "study_plans")
        os.makedirs(plans_folder, exist_ok=True)

        plan_file = os.path.join(plans_folder, f"{plan_id}.json")
        with open(plan_file, "w", encoding="utf-8") as f:
            json.dump({
                "plan_id": plan_id,
                "assessment_id": plan_request.assessment_id,
                "resource_id": resource_id,
                "plan": plan_result,
                "created_at": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

        # Send email if requested
        email_sent = False
        if plan_request.send_email and plan_request.email:
            email_sent = email_service.send_study_plan_email(plan_request.email, plan_result)

        return StudyPlanResponse(
            status="success",
            message="Personalized study plan generated successfully",
            plan_id=plan_id,
            plan=plan_result,
            email_sent=email_sent
        )

    except Exception as e:
        logger.error(f"Error generating study plan: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback", response_model=FeedbackResponse)
async def provide_feedback(
    request: Request,
    feedback: StudyPlanFeedback = Body(...),
):
    """
    Provide feedback on a study plan to refine future suggestions.
    """
    try:
        # Get the study plan
        plan_file = os.path.join("data", "study_plans", f"{feedback.plan_id}.json")
        if not os.path.exists(plan_file):
            raise HTTPException(status_code=404, detail="Study plan not found")

        with open(plan_file, "r", encoding="utf-8") as f:
            plan_data = json.load(f)

        # Get the assessment
        assessment_id = plan_data.get("assessment_id")
        assessment_file = os.path.join("data", "assessments", f"{assessment_id}_result.json")

        if os.path.exists(assessment_file):
            with open(assessment_file, "r", encoding="utf-8") as f:
                assessment = json.load(f)

            # Update the assessment with feedback
            assessment["feedback"] = {
                "rating": feedback.rating,
                "too_difficult": feedback.too_difficult,
                "too_easy": feedback.too_easy,
                "feedback": feedback.feedback,
                "comments": feedback.comments,
                "provided_at": datetime.now().isoformat()
            }

            # Save the updated assessment
            with open(assessment_file, "w", encoding="utf-8") as f:
                json.dump(assessment, f, ensure_ascii=False, indent=2)

        # Save the feedback
        feedback_folder = os.path.join("data", "feedback")
        os.makedirs(feedback_folder, exist_ok=True)

        feedback_file = os.path.join(feedback_folder, f"{feedback.plan_id}_feedback.json")
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump({
                "plan_id": feedback.plan_id,
                "rating": feedback.rating,
                "too_difficult": feedback.too_difficult,
                "too_easy": feedback.too_easy,
                "feedback": feedback.feedback,
                "comments": feedback.comments,
                "provided_at": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

        # Check if we need to adjust the plan
        updated_plan = None
        if feedback.too_difficult or feedback.too_easy:
            # Get the original plan
            original_plan = plan_data.get("plan", {})

            # Adjust the plan based on feedback
            if feedback.too_difficult:
                # Reduce difficulty
                updated_plan = adjust_plan_difficulty(original_plan, "decrease")
            elif feedback.too_easy:
                # Increase difficulty
                updated_plan = adjust_plan_difficulty(original_plan, "increase")

            if updated_plan:
                # Save the updated plan
                plan_data["plan"] = updated_plan
                plan_data["updated_at"] = datetime.now().isoformat()
                plan_data["feedback_applied"] = True

                with open(plan_file, "w", encoding="utf-8") as f:
                    json.dump(plan_data, f, ensure_ascii=False, indent=2)

        return FeedbackResponse(
            status="success",
            message="Feedback received and processed successfully",
            updated_plan=updated_plan
        )

    except Exception as e:
        logger.error(f"Error processing feedback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def generate_fallback_study_plan(assessment, resource_topics):
    """Generate a fallback study plan if Ollama fails"""

    learning_capacity = assessment.get("learning_capacity", 5)
    topics_per_day = assessment.get("topics_per_day", 3)

    # Create a basic template for the study plan
    plan = {
        "metadata": {
            "learning_capacity": learning_capacity,
            "topics_per_day": topics_per_day,
            "iq_score": assessment.get("iq_score", 100),
            "strengths": assessment.get("strengths", []),
            "weaknesses": assessment.get("weaknesses", []),
            "generated_at": datetime.now().isoformat()
        },
        "days": []
    }

    # Extract topics from resource_topics
    topics = [t["topic"] for t in resource_topics]

    # If we don't have enough topics, add some generic ones
    if len(topics) < topics_per_day * 14:
        generic_topics = [
            "Basic Concepts", "Fundamentals", "Core Principles",
            "Key Theories", "Essential Methods", "Primary Techniques",
            "Foundational Knowledge", "Main Ideas", "Critical Concepts",
            "Important Formulas", "Key Definitions", "Standard Procedures",
            "Common Applications", "Practical Examples", "Case Studies"
        ]
        topics.extend(generic_topics)

    # Generate 14 days of study plan
    for day in range(1, 15):
        # Select topics for the day
        day_topics = []
        for i in range(topics_per_day):
            topic_index = (day + i) % len(topics)
            day_topics.append(topics[topic_index])

        # Create activities based on learning capacity
        activities = []
        for topic in day_topics:
            if learning_capacity <= 3:
                activities.append(f"Read and summarize the main points about {topic}")
                activities.append(f"Create flashcards for key terms in {topic}")
                activities.append(f"Review {topic} notes before bed")
            elif learning_capacity <= 6:
                activities.append(f"Study and take detailed notes on {topic}")
                activities.append(f"Practice example problems related to {topic}")
                activities.append(f"Teach someone else about {topic}")
            else:
                activities.append(f"Deep dive into advanced concepts of {topic}")
                activities.append(f"Solve complex problems involving {topic}")
                activities.append(f"Research and write about applications of {topic}")

        # Create a study tip based on learning capacity
        if learning_capacity <= 3:
            tip = "Break down complex topics into smaller, manageable parts. Focus on understanding one concept at a time."
        elif learning_capacity <= 6:
            tip = "Try teaching the material to someone else or explaining it out loud to reinforce your understanding."
        else:
            tip = "Challenge yourself by finding connections between different topics and exploring advanced applications."

        # Add the day to the plan
        plan["days"].append({
            "date": f"Day {day}",
            "topics": day_topics,
            "activities": activities,
            "tip": tip,
            "estimated_time": 60 * topics_per_day  # minutes
        })

    return plan

def adjust_plan_difficulty(plan, direction):
    """Adjust the difficulty of a study plan based on feedback"""

    # Create a copy of the plan
    adjusted_plan = plan.copy()

    # Update metadata
    metadata = adjusted_plan.get("metadata", {})
    learning_capacity = metadata.get("learning_capacity", 5)
    topics_per_day = metadata.get("topics_per_day", 3)

    # Adjust learning capacity and topics per day
    if direction == "decrease":
        # Make it easier
        learning_capacity = max(1, learning_capacity - 1)
        topics_per_day = max(1, topics_per_day - 1)
    else:
        # Make it harder
        learning_capacity = min(10, learning_capacity + 1)
        topics_per_day = min(10, topics_per_day + 1)

    # Update metadata
    metadata["learning_capacity"] = learning_capacity
    metadata["topics_per_day"] = topics_per_day
    metadata["adjusted_based_on_feedback"] = True
    adjusted_plan["metadata"] = metadata

    # Adjust days
    days = adjusted_plan.get("days", [])
    for day in days:
        # Adjust topics
        topics = day.get("topics", [])
        if direction == "decrease" and len(topics) > topics_per_day:
            # Remove some topics
            day["topics"] = topics[:topics_per_day]
        elif direction == "increase" and len(topics) < topics_per_day:
            # Add generic topics
            generic_topics = [
                "Additional Topic 1",
                "Additional Topic 2",
                "Additional Topic 3",
                "Additional Topic 4",
                "Additional Topic 5"
            ]
            needed = topics_per_day - len(topics)
            day["topics"] = topics + generic_topics[:needed]

        # Adjust activities
        activities = day.get("activities", [])
        if direction == "decrease":
            # Simplify activities
            day["activities"] = [a.replace("advanced", "basic").replace("complex", "simple") for a in activities]
            # Add a simpler tip
            day["tip"] = "Focus on mastering the basics before moving on to more complex topics."
        else:
            # Make activities more challenging
            day["activities"] = [a.replace("basic", "advanced").replace("simple", "complex") for a in activities]
            # Add a more challenging tip
            day["tip"] = "Challenge yourself by exploring connections between topics and seeking out advanced applications."

    adjusted_plan["days"] = days
    return adjusted_plan
