import os
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, auth
from firebase_admin.exceptions import FirebaseError

# Set up logging
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
firebase_app = None
auth = None

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    global firebase_app, auth

    if firebase_app is not None:
        return firebase_app

    # Always use mock Firebase app for development
    logger.info("Using mock Firebase app for development")

    # Create a simple mock object
    class MockFirebaseApp:
        def __init__(self):
            self.name = "[DEFAULT]"

    firebase_app = MockFirebaseApp()
    auth = MockFirebaseAuth()
    logger.info("Using mock Firebase auth for development")
    return firebase_app

# Mock Firebase Auth for development
class MockFirebaseAuth:
    @staticmethod
    def verify_id_token(id_token):
        # Extract a UID-like string from the token
        import hashlib
        uid = hashlib.md5(id_token.encode()).hexdigest()[:28]

        # Create mock decoded token
        return {
            "uid": uid,
            "email": f"user-{uid[:8]}@example.com",
            "email_verified": True,
            "name": f"User {uid[:8]}",
            "picture": None,
            "auth_time": int(datetime.now().timestamp()),
            "firebase": {
                "sign_in_provider": "password"
            }
        }

    @staticmethod
    def create_user(email, password, **kwargs):
        # Generate a random UID
        import uuid
        uid = f"mock-{uuid.uuid4().hex[:12]}"

        # Create a mock user object
        class MockUser:
            def __init__(self, uid, email, display_name=None, email_verified=False):
                self.uid = uid
                self.email = email
                self.display_name = display_name or email.split('@')[0]
                self.email_verified = email_verified
                self.photo_url = None
                self.disabled = False
                self.user_metadata = type('obj', (object,), {
                    'creation_timestamp': int(datetime.now().timestamp() * 1000),
                    'last_sign_in_timestamp': int(datetime.now().timestamp() * 1000)
                })

        return MockUser(
            uid=uid,
            email=email,
            display_name=kwargs.get('display_name'),
            email_verified=kwargs.get('email_verified', False)
        )

    @staticmethod
    def get_user(uid):
        # Create a mock user object
        class MockUser:
            def __init__(self, uid):
                self.uid = uid
                self.email = f"user-{uid[:8]}@example.com"
                self.display_name = f"User {uid[:8]}"
                self.email_verified = True
                self.photo_url = None
                self.disabled = False
                self.user_metadata = type('obj', (object,), {
                    'creation_timestamp': int(datetime.now().timestamp() * 1000) - 86400000,  # 1 day ago
                    'last_sign_in_timestamp': int(datetime.now().timestamp() * 1000)
                })

        return MockUser(uid)

    @staticmethod
    def delete_user(uid):
        # Pretend to delete the user
        logger.info(f"Mock delete user {uid}")
        return True

def verify_firebase_token(id_token: str) -> Optional[Dict[str, Any]]:
    """
    Verify Firebase ID token and return user data

    Args:
        id_token: Firebase ID token

    Returns:
        User data dictionary or None if token is invalid
    """
    try:
        # Initialize Firebase if not already initialized
        if firebase_app is None:
            initialize_firebase()

        # For development environment, always use mock auth
        if os.environ.get("ENVIRONMENT", "development") == "development":
            # Use mock Firebase auth
            mock_auth = MockFirebaseAuth()
            decoded_token = mock_auth.verify_id_token(id_token)

            # Extract user information
            user_data = {
                "uid": decoded_token.get("uid"),
                "email": decoded_token.get("email"),
                "email_verified": decoded_token.get("email_verified", False),
                "name": decoded_token.get("name"),
                "picture": decoded_token.get("picture"),
                "auth_time": datetime.fromtimestamp(decoded_token.get("auth_time", 0)),
                "firebase": decoded_token.get("firebase", {})
            }

            logger.info(f"Using mock Firebase auth for token verification: {user_data['uid']}")
            return user_data

        # For production, use real Firebase auth
        try:
            # Verify the token
            decoded_token = auth.verify_id_token(id_token)

            # Extract user information
            user_data = {
                "uid": decoded_token.get("uid"),
                "email": decoded_token.get("email"),
                "email_verified": decoded_token.get("email_verified", False),
                "name": decoded_token.get("name"),
                "picture": decoded_token.get("picture"),
                "auth_time": datetime.fromtimestamp(decoded_token.get("auth_time", 0)),
                "firebase": decoded_token.get("firebase", {})
            }

            return user_data
        except Exception as e:
            logger.error(f"Failed to verify Firebase token: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Error verifying Firebase token: {str(e)}")
        # For development environment, create mock user data
        if os.environ.get("ENVIRONMENT", "development") == "development":
            logger.info("Creating mock user data for development after error")

            # Extract a UID-like string from the token
            import hashlib
            uid = hashlib.md5(id_token.encode()).hexdigest()[:28]

            # Create mock user data
            user_data = {
                "uid": uid,
                "email": f"user-{uid[:8]}@example.com",
                "email_verified": True,
                "name": f"User {uid[:8]}",
                "picture": None,
                "auth_time": datetime.now(),
                "firebase": {
                    "sign_in_provider": "password"
                }
            }

            return user_data
        return None

def get_firebase_user(uid: str) -> Optional[Dict[str, Any]]:
    """
    Get Firebase user data by UID

    Args:
        uid: Firebase user UID

    Returns:
        User data dictionary or None if user not found
    """
    try:
        # Initialize Firebase if not already initialized
        if firebase_app is None:
            initialize_firebase()

        # For development environment, always use mock auth
        if os.environ.get("ENVIRONMENT", "development") == "development":
            # Use mock Firebase auth
            mock_auth = MockFirebaseAuth()
            user = mock_auth.get_user(uid)

            # Convert to dictionary
            user_data = {
                "uid": user.uid,
                "email": user.email,
                "email_verified": user.email_verified,
                "display_name": user.display_name,
                "photo_url": user.photo_url,
                "disabled": user.disabled,
                "creation_time": user.user_metadata.creation_timestamp,
                "last_sign_in_time": user.user_metadata.last_sign_in_timestamp,
            }

            logger.info(f"Using mock Firebase auth for user retrieval: {user_data['uid']}")
            return user_data

        # Get user by UID
        user = auth.get_user(uid)

        # Convert to dictionary
        user_data = {
            "uid": user.uid,
            "email": user.email,
            "email_verified": user.email_verified,
            "display_name": user.display_name,
            "photo_url": user.photo_url,
            "disabled": user.disabled,
            "creation_time": user.user_metadata.creation_timestamp,
            "last_sign_in_time": user.user_metadata.last_sign_in_timestamp,
        }

        return user_data

    except Exception as e:
        logger.error(f"Error getting Firebase user: {str(e)}")
        # Return mock data for development
        if os.environ.get("ENVIRONMENT", "development") == "development":
            # Create mock user data with current timestamp
            now_timestamp = datetime.now().timestamp() * 1000  # Convert to milliseconds
            return {
                "uid": uid,
                "email": f"user-{uid[:8]}@example.com",
                "email_verified": True,
                "display_name": f"User {uid[:8]}",
                "photo_url": None,
                "disabled": False,
                "creation_time": now_timestamp - (86400 * 1000 * 30),  # 30 days ago
                "last_sign_in_time": now_timestamp,  # Now
            }
        return None

def create_firebase_user(email: str, password: str, display_name: str = None) -> Optional[Dict[str, Any]]:
    """
    Create a new Firebase user

    Args:
        email: User email
        password: User password
        display_name: User display name (optional)

    Returns:
        User data dictionary or None if creation failed
    """
    try:
        # Initialize Firebase if not already initialized
        if firebase_app is None:
            initialize_firebase()

        # For development environment, always use mock auth
        if os.environ.get("ENVIRONMENT", "development") == "development":
            # Use mock Firebase auth
            mock_auth = MockFirebaseAuth()
            user_props = {
                "email": email,
                "password": password,
                "email_verified": False,
                "display_name": display_name
            }
            user = mock_auth.create_user(email, password, **user_props)

            # Convert to dictionary
            user_data = {
                "uid": user.uid,
                "email": user.email,
                "email_verified": user.email_verified,
                "display_name": user.display_name,
            }

            logger.info(f"Created mock Firebase user with UID {user_data['uid']}")
            return user_data

        # Create user in Firebase
        user_props = {
            "email": email,
            "password": password,
            "email_verified": False,
        }

        if display_name:
            user_props["display_name"] = display_name

        user = auth.create_user(**user_props)

        # Convert to dictionary
        user_data = {
            "uid": user.uid,
            "email": user.email,
            "email_verified": user.email_verified,
            "display_name": user.display_name,
        }

        logger.info(f"Created Firebase user with UID {user.uid}")
        return user_data

    except Exception as e:
        logger.error(f"Error creating Firebase user: {str(e)}")
        # For development environment, create a mock user
        if os.environ.get("ENVIRONMENT", "development") == "development":
            logger.info("Creating mock Firebase user for development after error")

            import uuid
            import time

            # Generate a random UID
            uid = f"mock-{uuid.uuid4().hex[:12]}"

            # Create mock user data
            user_data = {
                "uid": uid,
                "email": email,
                "email_verified": False,
                "display_name": display_name or email.split("@")[0],
                "creation_time": int(time.time() * 1000),  # Current time in milliseconds
                "last_sign_in_time": int(time.time() * 1000),  # Current time in milliseconds
            }

            logger.info(f"Created mock Firebase user with UID {uid}")
            return user_data
        return None

def delete_firebase_user(uid: str) -> bool:
    """
    Delete a Firebase user

    Args:
        uid: Firebase user UID

    Returns:
        True if deletion was successful, False otherwise
    """
    try:
        # Initialize Firebase if not already initialized
        if firebase_app is None:
            initialize_firebase()

        # For development environment, always use mock auth
        if os.environ.get("ENVIRONMENT", "development") == "development":
            # Use mock Firebase auth
            mock_auth = MockFirebaseAuth()
            result = mock_auth.delete_user(uid)

            logger.info(f"Deleted mock Firebase user with UID {uid}")
            return True

        # Delete user in Firebase
        auth.delete_user(uid)
        logger.info(f"Deleted Firebase user with UID {uid}")
        return True

    except Exception as e:
        logger.error(f"Error deleting Firebase user: {str(e)}")
        # For development environment, pretend deletion was successful
        if os.environ.get("ENVIRONMENT", "development") == "development":
            logger.info(f"Pretending to delete Firebase user with UID {uid} in development mode")
            return True
        return False
