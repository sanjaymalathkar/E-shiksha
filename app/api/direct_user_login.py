import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.core.auth import verify_password
from app.core.mongodb import get_db
from app.models.mongodb_models import MongoDBUser
from app.core.firebase_auth import verify_firebase_token, get_firebase_user

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/direct-login", tags=["direct-login"])

class DirectLoginRequest(BaseModel):
    """Direct login request model"""
    firebase_uid: str
    email: str
    password: str
    client_ip: Optional[str] = None

class UserResponse(BaseModel):
    """User response model"""
    firebase_uid: str
    username: str
    email: str
    display_name: Optional[str] = None
    mobile_number: Optional[str] = None
    role: str
    auth_provider: str = "email"
    email_verified: bool = False
    last_login: Optional[datetime] = None
    login_count: Optional[int] = None

@router.post("/verify", response_model=UserResponse)
async def verify_login(login_request: DirectLoginRequest, request: Request):
    """
    Verify login credentials directly in MongoDB
    
    This endpoint:
    1. Checks if the user exists in MongoDB by Firebase UID
    2. Verifies the password against the stored hash
    3. Updates login timestamps in MongoDB
    4. Returns user information
    """
    try:
        # Get client IP address
        client_ip = login_request.client_ip or request.client.host
        
        # Get MongoDB database
        db = get_db()
        users_collection = db["users"]
        
        # Find user by Firebase UID
        user_doc = users_collection.find_one({"firebase_uid": login_request.firebase_uid})
        if not user_doc:
            logger.warning(f"User with Firebase UID {login_request.firebase_uid} not found in MongoDB")
            raise HTTPException(status_code=404, detail="User not found")
        
        # Convert to MongoDBUser model
        user = MongoDBUser(**user_doc)
        
        # Verify password if user has a password hash
        if user.password_hash:
            if not verify_password(login_request.password, user.password_hash):
                logger.warning(f"Password verification failed for user {user.username}")
                raise HTTPException(status_code=401, detail="Invalid credentials")
            logger.info(f"Password verification successful for user {user.username}")
        else:
            # If user doesn't have a password hash, create one
            from app.core.auth import get_password_hash
            password_hash = get_password_hash(login_request.password)
            
            # Update user with password hash
            users_collection.update_one(
                {"firebase_uid": user.firebase_uid},
                {"$set": {"password_hash": password_hash}}
            )
            logger.info(f"Added password hash to MongoDB user {user.username}")
        
        # Update login information
        now = datetime.utcnow()
        update_data = {
            "last_login": now,
            "updated_at": now,
            "login_count": user.login_count + 1
        }
        
        if client_ip:
            update_data["last_login_ip"] = client_ip
        
        # Update user
        users_collection.update_one(
            {"firebase_uid": user.firebase_uid},
            {"$set": update_data}
        )
        
        logger.info(f"Updated login information for user {user.username}")
        
        # Mark attendance
        try:
            from app.core.attendance_service import AttendanceService
            
            AttendanceService.mark_attendance(
                user_id=user.firebase_uid,
                username=user.username,
                email=user.email,
                status="present",
                login_time=now
            )
        except Exception as e:
            # Log error but don't fail login if attendance marking fails
            logger.error(f"Error marking attendance: {str(e)}")
        
        # Return user information
        return UserResponse(
            firebase_uid=user.firebase_uid,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            mobile_number=user.mobile_number,
            role=user.role,
            auth_provider=user.auth_provider,
            email_verified=user.email_verified,
            last_login=now,
            login_count=user.login_count + 1
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error and return a generic error message
        logger.error(f"Error verifying login: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to verify login")
