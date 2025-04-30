from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, auth
import os
import logging

# Setup logger
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
def init_firebase_admin():
    """Initialize Firebase Admin SDK"""
    try:
        # Check if Firebase Admin is already initialized
        firebase_admin.get_app()
        logger.info("Firebase Admin SDK already initialized")
        return
    except ValueError:
        # If not, initialize it
        pass

    # For development, create a mock app with minimal configuration
    # This allows the app to run without a real Firebase project
    app_options = {
        "projectId": "e-shiksha-dev",
        "storageBucket": "e-shiksha-dev.appspot.com",
    }

    try:
        # Use a mock credential for development
        firebase_admin.initialize_app(options=app_options)
        logger.info("Firebase Admin SDK initialized with mock credentials")
    except Exception as e:
        logger.error(f"Error initializing Firebase Admin SDK: {str(e)}")
        # Continue without Firebase - will use fallback authentication

# Initialize Firebase Admin SDK
init_firebase_admin()

# HTTP Bearer token scheme
security = HTTPBearer()

async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Verify Firebase ID token and return user info

    In development mode, this will return mock user info if Firebase authentication fails.
    """
    token = credentials.credentials

    # Check if we're in development mode
    dev_mode = os.environ.get("ENVIRONMENT", "development") == "development"

    try:
        # Verify the ID token
        decoded_token = auth.verify_id_token(token)

        # Get user info
        user_info = {
            "uid": decoded_token["uid"],
            "email": decoded_token.get("email", ""),
            "name": decoded_token.get("name", ""),
            "picture": decoded_token.get("picture", ""),
            "email_verified": decoded_token.get("email_verified", False)
        }

        return user_info

    except Exception as e:
        logger.error(f"Error verifying Firebase token: {str(e)}")

        # In development mode, return mock user info
        if dev_mode:
            logger.warning("Using mock user info for development")
            return {
                "uid": "mock-user-123",
                "email": "demo@example.com",
                "name": "Demo User",
                "picture": "",
                "email_verified": True
            }

        # In production, raise an exception
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )

# Optional security for endpoints that can use either session or token auth
class OptionalHTTPBearer(HTTPBearer):
    async def __call__(self, request: Request):
        try:
            return await super().__call__(request)
        except HTTPException:
            return None

optional_security = OptionalHTTPBearer()
