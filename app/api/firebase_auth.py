import os
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.core.firebase_auth import verify_firebase_token, get_firebase_user
from app.core.user_service import UserService
from app.models.mongodb_models import MongoDBUser
from app.core.mongodb import get_db
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/firebase-auth", tags=["firebase-auth"])

# Firebase configuration endpoint
@router.get("/config")
async def get_firebase_config():
    """
    Get Firebase configuration for client-side initialization

    This endpoint returns the Firebase configuration needed to initialize
    the Firebase SDK on the client side.
    """
    # Get Firebase configuration from environment variables
    firebase_config = os.getenv("FIREBASE_CONFIG")

    if firebase_config:
        try:
            # Parse JSON configuration
            config = json.loads(firebase_config)
            return config
        except json.JSONDecodeError:
            raise HTTPException(status_code=500, detail="Invalid Firebase configuration format")
    else:
        # Fallback to individual environment variables
        config = {
            "apiKey": os.getenv("FIREBASE_API_KEY"),
            "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
            "projectId": os.getenv("FIREBASE_PROJECT_ID"),
            "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
            "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
            "appId": os.getenv("FIREBASE_APP_ID"),
            "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID")
        }

        # Remove None values
        config = {k: v for k, v in config.items() if v is not None}

        if not config.get("apiKey"):
            raise HTTPException(status_code=500, detail="Firebase configuration not available")

        return config

# Security scheme for Firebase token
security = HTTPBearer()

class FirebaseAuthRequest(BaseModel):
    """Firebase authentication request"""
    id_token: str
    username: Optional[str] = None
    mobile_number: Optional[str] = None
    password: Optional[str] = None
    client_ip: Optional[str] = None

class CreateUserRequest(BaseModel):
    """Create user request model"""
    email: str
    password: str
    username: str
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
    last_login: Optional[datetime] = None
    login_count: Optional[int] = None

@router.post("/create", response_model=UserResponse)
async def create_user(user_request: CreateUserRequest, request: Request):
    """
    Create a new user in both Firebase and MongoDB

    This endpoint:
    1. Creates a new user in Firebase Authentication
    2. Creates a corresponding user in MongoDB with the same credentials
    3. Returns the created user information
    """
    try:
        # Get client IP address
        client_ip = user_request.client_ip or request.client.host

        # Create user in Firebase
        from app.core.firebase_auth import create_firebase_user
        firebase_user = create_firebase_user(
            email=user_request.email,
            password=user_request.password,
            display_name=user_request.display_name or user_request.username
        )

        if not firebase_user:
            raise HTTPException(status_code=500, detail="Failed to create user in Firebase")

        logger.info(f"Created user in Firebase with UID {firebase_user['uid']}")

        # Hash password for MongoDB storage - using the SAME password as Firebase
        from app.core.auth import get_password_hash
        password_hash = get_password_hash(user_request.password)

        # Create user in MongoDB with the same credentials
        user = UserService.create_user(
            firebase_uid=firebase_user["uid"],
            username=user_request.username,
            email=user_request.email,
            role=user_request.role,
            display_name=user_request.display_name or user_request.username,
            mobile_number=user_request.mobile_number,
            password_hash=password_hash,  # Store the same password hash in MongoDB
            auth_provider="email",
            email_verified=firebase_user.get("email_verified", False)
        )

        if not user:
            # If MongoDB creation fails, try to delete the Firebase user to maintain consistency
            from app.core.firebase_auth import delete_firebase_user
            delete_firebase_user(firebase_user["uid"])
            raise HTTPException(status_code=500, detail="Failed to create user in MongoDB")

        logger.info(f"Created user in MongoDB with username {user.username} and Firebase UID {user.firebase_uid}")
        logger.info(f"Double authentication is now set up for user {user.username}")

        # Set initial login time
        login_time = datetime.utcnow()

        # Update user login information in MongoDB
        UserService.update_user_login(
            firebase_uid=user.firebase_uid,
            login_time=login_time,
            client_ip=client_ip
        )

        # Return user information
        return UserResponse(
            firebase_uid=user.firebase_uid,
            username=user.username,
            email=user.email,
            display_name=user.display_name,
            mobile_number=user.mobile_number,
            role=user.role,
            auth_provider="email",
            email_verified=firebase_user.get("email_verified", False),
            last_login=login_time,
            login_count=1
        )

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log the error and return a generic error message
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create user")

@router.post("/login", response_model=UserResponse)
async def firebase_login(auth_request: FirebaseAuthRequest, request: Request):
    """
    Login with Firebase ID token and MongoDB credentials (double security check)

    This endpoint:
    1. Verifies the Firebase ID token
    2. Checks MongoDB credentials if provided (except for Google sign-in)
    3. Updates login timestamps in MongoDB
    4. Marks attendance based on login timestamp
    5. Returns user information
    """
    # Get client IP address
    client_ip = auth_request.client_ip or request.client.host

    # Verify Firebase token
    user_data = verify_firebase_token(auth_request.id_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")

    # Hash password if provided
    password_hash = None
    if auth_request.password:
        from app.core.auth import get_password_hash
        password_hash = get_password_hash(auth_request.password)

    # Determine auth provider from token
    auth_provider = "email"  # Default
    if "firebase" in user_data and "sign_in_provider" in user_data["firebase"]:
        auth_provider = user_data["firebase"]["sign_in_provider"]
    elif "provider_id" in user_data:
        auth_provider = user_data["provider_id"]

    # Check if this is a Google sign-in
    is_google_auth = auth_provider == "google.com"

    # Get or create user in MongoDB
    user = UserService.get_or_create_user_from_firebase(
        firebase_uid=user_data["uid"],
        username=auth_request.username,
        mobile_number=auth_request.mobile_number,
        password_hash=password_hash,
        auth_provider=auth_provider
    )

    if not user:
        raise HTTPException(status_code=500, detail="Failed to get or create user")

    # Double security check: Verify MongoDB credentials for non-Google auth
    if not is_google_auth:  # Skip double auth for Google sign-in
        if auth_request.password:
            # If user has a password hash in MongoDB, verify it
            if user.password_hash:
                from app.core.auth import verify_password
                if not verify_password(auth_request.password, user.password_hash):
                    logger.warning(f"MongoDB password verification failed for user {user.username}")
                    raise HTTPException(status_code=401, detail="Invalid MongoDB credentials")
                logger.info(f"MongoDB password verification successful for user {user.username}")
            else:
                # If user doesn't have a password hash yet, create one
                from app.core.auth import get_password_hash
                password_hash = get_password_hash(auth_request.password)

                # Update user with password hash
                db = get_db()
                users_collection = db["users"]
                users_collection.update_one(
                    {"firebase_uid": user.firebase_uid},
                    {"$set": {"password_hash": password_hash}}
                )
                logger.info(f"Added password hash to MongoDB user {user.username}")
        else:
            # If no password provided but user has a password hash, require password
            if user.password_hash:
                logger.warning(f"Password required for user {user.username} with existing password hash")
                raise HTTPException(status_code=401, detail="Password required for double authentication")
    else:
        logger.info(f"Skipping double authentication for Google sign-in user {user.username}")

    # Get Firebase user data for login timestamp
    firebase_user = get_firebase_user(user.firebase_uid)

    # Get login timestamp from Firebase
    login_time = datetime.utcnow()
    if firebase_user and "last_sign_in_time" in firebase_user:
        if isinstance(firebase_user["last_sign_in_time"], (int, float)):
            login_time = datetime.fromtimestamp(firebase_user["last_sign_in_time"] / 1000)
        else:
            login_time = firebase_user["last_sign_in_time"]

    # Update user login information in MongoDB
    UserService.update_user_login(
        firebase_uid=user.firebase_uid,
        login_time=login_time,
        client_ip=client_ip
    )

    # Mark attendance based on login timestamp
    try:
        from app.core.attendance_service import AttendanceService

        AttendanceService.mark_attendance(
            user_id=user.firebase_uid,
            username=user.username,
            email=user.email,
            status="present",
            login_time=login_time
        )
    except Exception as e:
        # Log error but don't fail login if attendance marking fails
        logger.error(f"Error marking attendance: {str(e)}")

    # Return user information with login details
    return UserResponse(
        firebase_uid=user.firebase_uid,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        mobile_number=user.mobile_number,
        role=user.role,
        auth_provider=user.auth_provider,
        email_verified=user.email_verified,
        last_login=login_time,
        login_count=user.login_count
    )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> MongoDBUser:
    """
    Get current user from Firebase token

    This dependency verifies the Firebase ID token and returns the corresponding MongoDB user.
    """
    # Get token from Authorization header
    token = credentials.credentials

    # Verify Firebase token
    user_data = verify_firebase_token(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid Firebase token")

    # Get user from MongoDB
    user = UserService.get_user_by_firebase_uid(user_data["uid"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: MongoDBUser = Depends(get_current_user)):
    """
    Get current user information

    This endpoint returns information about the currently authenticated user.
    """
    return UserResponse(
        firebase_uid=current_user.firebase_uid,
        username=current_user.username,
        email=current_user.email,
        display_name=current_user.display_name,
        mobile_number=current_user.mobile_number,
        role=current_user.role,
        last_login=current_user.last_login,
        login_count=current_user.login_count
    )
