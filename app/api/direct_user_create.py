import logging
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.core.auth import get_password_hash
from app.core.mongodb import get_db
from app.models.mongodb_models import MongoDBUser

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/direct-user", tags=["direct-user"])

class DirectUserCreateRequest(BaseModel):
    """Direct user creation request model"""
    firebase_uid: str
    username: str
    email: str
    password: str
    display_name: Optional[str] = None
    mobile_number: Optional[str] = None
    role: str = "student"
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
    created_at: datetime
    updated_at: datetime

@router.post("/create", response_model=UserResponse)
async def create_user_direct(user_request: DirectUserCreateRequest, request: Request):
    """
    Create a new user directly in MongoDB
    
    This endpoint:
    1. Creates a user in MongoDB with the provided Firebase UID
    2. Returns the created user information
    """
    try:
        # Get client IP address
        client_ip = user_request.client_ip or request.client.host
        
        # Get MongoDB database
        db = get_db()
        users_collection = db["users"]
        
        # Check if user already exists
        existing_user = users_collection.find_one({"firebase_uid": user_request.firebase_uid})
        if existing_user:
            logger.warning(f"User with Firebase UID {user_request.firebase_uid} already exists")
            raise HTTPException(status_code=400, detail="User already exists")
        
        # Check if username is taken
        username_exists = users_collection.find_one({"username": user_request.username})
        if username_exists:
            logger.warning(f"Username {user_request.username} is already taken")
            raise HTTPException(status_code=400, detail="Username already taken")
        
        # Check if email is taken
        email_exists = users_collection.find_one({"email": user_request.email})
        if email_exists:
            logger.warning(f"Email {user_request.email} is already taken")
            raise HTTPException(status_code=400, detail="Email already taken")
        
        # Hash password
        password_hash = get_password_hash(user_request.password)
        
        # Create user document
        now = datetime.utcnow()
        user_doc = {
            "firebase_uid": user_request.firebase_uid,
            "username": user_request.username,
            "email": user_request.email,
            "display_name": user_request.display_name or user_request.username,
            "mobile_number": user_request.mobile_number,
            "password_hash": password_hash,
            "role": user_request.role,
            "auth_provider": "email",
            "email_verified": False,
            "last_login": now,
            "last_login_ip": client_ip,
            "login_count": 1,
            "created_at": now,
            "updated_at": now
        }
        
        # Insert user into MongoDB
        result = users_collection.insert_one(user_doc)
        
        if not result.inserted_id:
            logger.error(f"Failed to create user {user_request.username} in MongoDB")
            raise HTTPException(status_code=500, detail="Failed to create user in MongoDB")
        
        logger.info(f"Created user {user_request.username} with Firebase UID {user_request.firebase_uid} in MongoDB")
        
        # Return user information
        return UserResponse(
            firebase_uid=user_request.firebase_uid,
            username=user_request.username,
            email=user_request.email,
            display_name=user_request.display_name or user_request.username,
            mobile_number=user_request.mobile_number,
            role=user_request.role,
            auth_provider="email",
            email_verified=False,
            created_at=now,
            updated_at=now
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error and return a generic error message
        logger.error(f"Error creating user directly in MongoDB: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create user")
