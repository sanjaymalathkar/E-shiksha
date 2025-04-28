from fastapi import APIRouter, HTTPException, Body, Request
from pydantic import BaseModel, EmailStr
from typing import Dict, Any, Optional
import logging
from app.core.email import email_service

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/email",
    tags=["email"],
    responses={404: {"description": "Not found"}},
)

class EmailRequest(BaseModel):
    email: EmailStr
    study_plan_id: Optional[str] = None
    user_id: Optional[str] = None

class EmailResponse(BaseModel):
    status: str
    message: str

@router.post("/send-study-plan", response_model=EmailResponse)
async def send_study_plan_email(
    request: Request,
    email_request: EmailRequest = Body(...),
):
    """
    Send a study plan email to a user
    """
    try:
        # Check if email service is configured
        if not email_service.is_configured:
            return EmailResponse(
                status="warning",
                message="Email service not configured. Please set SMTP_USERNAME and SMTP_PASSWORD environment variables."
            )
        
        # Get study plan from session storage or database
        # In a real application, you would retrieve the study plan from a database
        # For now, we'll use a mock study plan
        study_plan = {
            "metadata": {
                "dlc_score": 7,
                "topics_per_day": 5,
                "exam_type": "General",
                "exam_date": "2023-12-31",
                "generated_at": "2023-06-01T12:00:00Z"
            },
            "days": [
                {
                    "date": "2023-06-01",
                    "topics": [
                        "Introduction to Algebra",
                        "Basic Geometry Concepts",
                        "Fundamental Physics Laws",
                        "Cell Biology Basics",
                        "Introduction to Chemistry"
                    ],
                    "activities": [
                        "Read Chapter 1 of Algebra textbook",
                        "Solve 10 practice problems on geometry",
                        "Watch video lecture on Newton's laws",
                        "Create flashcards for cell organelles",
                        "Complete chemistry worksheet"
                    ],
                    "tip": "Start with the most challenging topic when your mind is fresh, then move to easier topics."
                }
            ]
        }
        
        # Send email
        success = email_service.send_study_plan_email(email_request.email, study_plan)
        
        if success:
            return EmailResponse(
                status="success",
                message=f"Study plan email sent to {email_request.email}"
            )
        else:
            return EmailResponse(
                status="error",
                message="Failed to send email. Please check logs for details."
            )
    except Exception as e:
        logger.error(f"Error sending study plan email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
