from fastapi import APIRouter, HTTPException, Request, Body, Depends, status
from fastapi.security import HTTPAuthorizationCredentials
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, EmailStr
import logging
import os
from app.core.study_plan_service import StudyPlanService
from app.auth.firebase_auth import get_current_user, optional_security

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/daily-email",
    tags=["daily-email"],
    responses={404: {"description": "Not found"}},
)

class EmailResponse(BaseModel):
    status: str
    message: str
    emails_sent: int = 0

@router.post("/send-all", response_model=EmailResponse)
async def send_all_daily_emails(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(optional_security)
):
    """
    Send daily topic emails to all users with study plans

    This endpoint is for testing purposes and requires authentication in production.
    """
    try:
        # Check if we're in development mode
        dev_mode = os.environ.get("ENVIRONMENT", "development") == "development"

        # In production, check authentication
        if not dev_mode and credentials:
            try:
                # Get user data
                from app.auth.firebase_auth import auth
                token = credentials.credentials
                user_data = auth.verify_id_token(token)

                # Check if user is authorized (admin role)
                if user_data.get("role") != "admin" and user_data.get("email") != "demo@example.com":
                    raise HTTPException(
                        status_code=403,
                        detail="Only administrators can send emails to all users"
                    )
            except Exception as auth_error:
                logger.error(f"Authentication error: {str(auth_error)}")
                raise HTTPException(
                    status_code=401,
                    detail="Authentication failed"
                )
        elif not dev_mode:
            # In production, require authentication
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )

        # Send daily topic emails
        emails_sent = await StudyPlanService.send_daily_topic_emails()

        return EmailResponse(
            status="success",
            message=f"Sent {emails_sent} daily topic emails",
            emails_sent=emails_sent
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error sending daily topic emails: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/send-to-user", response_model=EmailResponse)
async def send_daily_email_to_user(
    request: Request,
    user_id: str = Body(...),
    credentials: HTTPAuthorizationCredentials = Depends(optional_security)
):
    """
    Send daily topic email to a specific user

    This endpoint is for testing purposes and requires authentication in production.
    """
    try:
        # Check if we're in development mode
        dev_mode = os.environ.get("ENVIRONMENT", "development") == "development"

        # In production, check authentication
        if not dev_mode and credentials:
            try:
                # Get user data
                from app.auth.firebase_auth import auth
                token = credentials.credentials
                user_data = auth.verify_id_token(token)

                # Check if user is authorized (admin role or sending to self)
                if user_data.get("role") != "admin" and user_data.get("uid") != user_id and user_data.get("email") != "demo@example.com":
                    raise HTTPException(
                        status_code=403,
                        detail="You can only send emails to yourself unless you are an administrator"
                    )
            except Exception as auth_error:
                logger.error(f"Authentication error: {str(auth_error)}")
                raise HTTPException(
                    status_code=401,
                    detail="Authentication failed"
                )
        elif not dev_mode:
            # In production, require authentication
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )

        # Get today's topics
        today_plan = StudyPlanService.get_todays_topics(user_id)

        if not today_plan:
            return EmailResponse(
                status="warning",
                message=f"No topics found for today for user {user_id}",
                emails_sent=0
            )

        # Get user from UserService
        from app.core.user_service import UserService
        user = UserService.get_user_by_firebase_uid(user_id)

        # In development mode, if user not found, create a mock user
        if not user and dev_mode:
            from app.models.user import User
            user = User(
                id=1,
                username="demo_user",
                email=f"{user_id}@example.com" if "@" not in user_id else user_id,
                display_name="Demo User",
                firebase_uid=user_id
            )
        elif not user:
            return EmailResponse(
                status="warning",
                message=f"User {user_id} not found",
                emails_sent=0
            )

        # Send email
        email_sent = StudyPlanService.send_daily_topic_email(
            user_email=user.email,
            user_name=user.display_name or user.username,
            today_plan=today_plan
        )

        if email_sent:
            return EmailResponse(
                status="success",
                message=f"Daily topic email sent to {user.email}",
                emails_sent=1
            )
        else:
            return EmailResponse(
                status="error",
                message=f"Failed to send daily topic email to {user.email}",
                emails_sent=0
            )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error sending daily topic email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/preview/{user_id}", response_model=Dict[str, Any])
async def preview_daily_email(
    request: Request,
    user_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(optional_security)
):
    """
    Preview the daily topic email for a user

    This endpoint is for testing purposes and requires authentication in production.
    """
    try:
        # Check if we're in development mode
        dev_mode = os.environ.get("ENVIRONMENT", "development") == "development"

        # In production, check authentication
        if not dev_mode and credentials:
            try:
                # Get user data
                from app.auth.firebase_auth import auth
                token = credentials.credentials
                user_data = auth.verify_id_token(token)

                # Check if user is authorized (admin role or previewing self)
                if user_data.get("role") != "admin" and user_data.get("uid") != user_id and user_data.get("email") != "demo@example.com":
                    raise HTTPException(
                        status_code=403,
                        detail="You can only preview your own email unless you are an administrator"
                    )
            except Exception as auth_error:
                logger.error(f"Authentication error: {str(auth_error)}")
                raise HTTPException(
                    status_code=401,
                    detail="Authentication failed"
                )
        elif not dev_mode:
            # In production, require authentication
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )

        # Get today's topics
        today_plan = StudyPlanService.get_todays_topics(user_id)

        if not today_plan:
            raise HTTPException(
                status_code=404,
                detail=f"No topics found for today for user {user_id}"
            )

        return {
            "status": "success",
            "message": "Daily topic email preview",
            "today_plan": today_plan
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error previewing daily topic email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
