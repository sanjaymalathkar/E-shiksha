import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.core.mongodb import get_db
from app.core.firebase_auth import verify_firebase_token

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user", tags=["user"])

class TrackLoginRequest(BaseModel):
    """Track login request model"""
    firebase_uid: str
    email: str
    client_ip: Optional[str] = None

class StoreProfileRequest(BaseModel):
    """Store profile request model"""
    firebase_uid: str
    email: str
    username: str
    display_name: Optional[str] = None
    mobile_number: Optional[str] = None
    role: str = "student"
    client_ip: Optional[str] = None

@router.post("/track-login")
async def track_login(request: Request, track_request: TrackLoginRequest):
    """
    Track user login in MongoDB (for analytics only, no verification)

    This endpoint:
    1. Stores login information in MongoDB
    2. Updates user login timestamps
    3. Marks attendance based on login timestamp
    """
    try:
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid Authorization header")
            return {"status": "warning", "message": "Login tracked anonymously"}

        # Extract token
        token = auth_header.split(" ")[1]

        # Verify Firebase token (lightweight check)
        user_data = verify_firebase_token(token)
        if not user_data or user_data.get("uid") != track_request.firebase_uid:
            logger.warning(f"Invalid Firebase token for user {track_request.firebase_uid}")
            return {"status": "warning", "message": "Login tracked anonymously"}

        # Get client IP address
        client_ip = track_request.client_ip or request.client.host

        # Get MongoDB database
        db = get_db()
        if db is None:
            logger.error("Failed to get MongoDB database")
            return {"status": "error", "message": "Database connection error"}

        users_collection = db["users"]

        # Get current time
        now = datetime.utcnow()

        # Find user in MongoDB
        user = users_collection.find_one({"firebase_uid": track_request.firebase_uid})

        if user:
            # Update existing user
            update_data = {
                "last_login": now,
                "last_login_ip": client_ip,
                "login_count": user.get("login_count", 0) + 1,
                "updated_at": now
            }

            users_collection.update_one(
                {"firebase_uid": track_request.firebase_uid},
                {"$set": update_data}
            )

            logger.info(f"Updated login information for existing user {track_request.firebase_uid}")
        else:
            # Create new user record
            new_user = {
                "firebase_uid": track_request.firebase_uid,
                "email": track_request.email,
                "username": track_request.email.split("@")[0],  # Default username from email
                "display_name": None,
                "mobile_number": None,
                "role": "student",
                "auth_provider": "firebase",  # Using Firebase only
                "email_verified": True,  # Assume verified since we got a valid token
                "last_login": now,
                "last_login_ip": client_ip,
                "login_count": 1,
                "created_at": now,
                "updated_at": now
            }

            users_collection.insert_one(new_user)

            logger.info(f"Created new user record for {track_request.firebase_uid}")

        # Mark attendance
        try:
            from app.core.attendance_service import AttendanceService

            AttendanceService.mark_attendance(
                user_id=track_request.firebase_uid,
                username=user.get("username") if user else track_request.email.split("@")[0],
                email=track_request.email,
                status="present",
                login_time=now
            )

            logger.info(f"Marked attendance for user {track_request.firebase_uid}")
        except Exception as e:
            logger.error(f"Error marking attendance: {str(e)}")

        return {"status": "success", "message": "Login tracked successfully"}

    except Exception as e:
        logger.error(f"Error tracking login: {str(e)}")
        return {"status": "error", "message": "Failed to track login"}

@router.post("/store-profile")
async def store_profile(request: Request, profile_request: StoreProfileRequest):
    """
    Store user profile data in MongoDB (for profile only, not for authentication)

    This endpoint:
    1. Stores or updates user profile information in MongoDB
    2. Does not affect authentication (which is handled by Firebase only)
    """
    try:
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("Missing or invalid Authorization header")
            return {"status": "error", "message": "Invalid authorization"}

        # Extract token
        token = auth_header.split(" ")[1]

        # Verify Firebase token
        user_data = verify_firebase_token(token)
        if not user_data or user_data.get("uid") != profile_request.firebase_uid:
            logger.warning(f"Invalid Firebase token for user {profile_request.firebase_uid}")
            return {"status": "error", "message": "Invalid authorization"}

        # Get client IP address
        client_ip = profile_request.client_ip or request.client.host

        # Get MongoDB database
        db = get_db()
        if db is None:
            logger.error("Failed to get MongoDB database")
            return {"status": "error", "message": "Database connection error"}

        users_collection = db["users"]

        # Get current time
        now = datetime.utcnow()

        # Find user in MongoDB
        user = users_collection.find_one({"firebase_uid": profile_request.firebase_uid})

        if user:
            # Update existing user
            update_data = {
                "username": profile_request.username,
                "display_name": profile_request.display_name,
                "mobile_number": profile_request.mobile_number,
                "role": profile_request.role,
                "updated_at": now
            }

            users_collection.update_one(
                {"firebase_uid": profile_request.firebase_uid},
                {"$set": update_data}
            )

            logger.info(f"Updated profile for existing user {profile_request.firebase_uid}")
        else:
            # Create new user record
            new_user = {
                "firebase_uid": profile_request.firebase_uid,
                "email": profile_request.email,
                "username": profile_request.username,
                "display_name": profile_request.display_name,
                "mobile_number": profile_request.mobile_number,
                "role": profile_request.role,
                "auth_provider": "firebase",  # Using Firebase only
                "email_verified": True,  # Assume verified since we got a valid token
                "last_login": now,
                "last_login_ip": client_ip,
                "login_count": 1,
                "created_at": now,
                "updated_at": now
            }

            users_collection.insert_one(new_user)

            logger.info(f"Created new user profile for {profile_request.firebase_uid}")

        return {"status": "success", "message": "Profile stored successfully"}

    except Exception as e:
        logger.error(f"Error storing profile: {str(e)}")
        return {"status": "error", "message": "Failed to store profile"}
