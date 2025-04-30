import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.mongodb import get_db
from app.core.firebase_auth import get_firebase_user
from app.models.mongodb_models import MongoDBUser

# Set up logging
logger = logging.getLogger(__name__)

class UserService:
    """Service for managing users in MongoDB"""

    @staticmethod
    def create_user(firebase_uid: str, username: str, email: str, role: str,
                   display_name: str = None, mobile_number: str = None,
                   password_hash: str = None, auth_provider: str = "email",
                   email_verified: bool = False) -> Optional[MongoDBUser]:
        """
        Create a new user in MongoDB

        Args:
            firebase_uid: Firebase UID
            username: Username
            email: Email address
            role: User role ('student' or 'teacher')
            display_name: Display name (optional)
            mobile_number: Mobile number (optional)
            password_hash: Hashed password (required)
            auth_provider: Authentication provider (email, google, etc.)
            email_verified: Whether the email has been verified

        Returns:
            Created MongoDBUser object or None if creation failed
        """
        try:
            # Get MongoDB database
            db = get_db()
            users_collection = db["users"]

            # Check if user already exists
            existing_user = users_collection.find_one({"firebase_uid": firebase_uid})
            if existing_user:
                logger.warning(f"User with Firebase UID {firebase_uid} already exists")
                return None

            # Check if username is taken
            username_exists = users_collection.find_one({"username": username})
            if username_exists:
                logger.warning(f"Username {username} is already taken")
                return None

            # Check if email is taken
            email_exists = users_collection.find_one({"email": email})
            if email_exists:
                logger.warning(f"Email {email} is already taken")
                return None

            # Ensure we have a password hash
            if not password_hash:
                from app.core.auth import get_password_hash
                # Generate a random password if none provided (for OAuth users)
                import secrets
                random_password = secrets.token_urlsafe(16)
                password_hash = get_password_hash(random_password)
                logger.info(f"Generated random password hash for user {username}")

            # Create user object
            user = MongoDBUser(
                firebase_uid=firebase_uid,
                username=username,
                email=email,
                display_name=display_name or username,
                mobile_number=mobile_number,
                password_hash=password_hash,
                role=role,
                email_verified=email_verified,
                auth_provider=auth_provider,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            # Insert user into MongoDB
            result = users_collection.insert_one(user.dict())

            if result.inserted_id:
                logger.info(f"Created user {username} with Firebase UID {firebase_uid} in MongoDB")
                return user
            else:
                logger.error(f"Failed to create user {username} with Firebase UID {firebase_uid} in MongoDB")
                return None

        except Exception as e:
            logger.error(f"Error creating user in MongoDB: {str(e)}")
            return None

    @staticmethod
    def get_user_by_firebase_uid(firebase_uid: str) -> Optional[MongoDBUser]:
        """
        Get a user by Firebase UID

        Args:
            firebase_uid: Firebase UID

        Returns:
            MongoDBUser object or None if user not found
        """
        try:
            # Get MongoDB database
            db = get_db()
            users_collection = db["users"]

            # Find user by Firebase UID
            user_data = users_collection.find_one({"firebase_uid": firebase_uid})

            if user_data:
                return MongoDBUser(**user_data)
            else:
                return None

        except Exception as e:
            logger.error(f"Error getting user by Firebase UID {firebase_uid}: {str(e)}")
            return None

    @staticmethod
    def get_user_by_username(username: str) -> Optional[MongoDBUser]:
        """
        Get a user by username

        Args:
            username: Username

        Returns:
            MongoDBUser object or None if user not found
        """
        try:
            # Get MongoDB database
            db = get_db()
            users_collection = db["users"]

            # Find user by username
            user_data = users_collection.find_one({"username": username})

            if user_data:
                return MongoDBUser(**user_data)
            else:
                return None

        except Exception as e:
            logger.error(f"Error getting user by username {username}: {str(e)}")
            return None

    @staticmethod
    def get_or_create_user_from_firebase(firebase_uid: str, username: str = None,
                                        mobile_number: str = None, password_hash: str = None,
                                        auth_provider: str = "email") -> Optional[MongoDBUser]:
        """
        Get a user by Firebase UID or create a new one if not found

        Args:
            firebase_uid: Firebase UID
            username: Username (required for new users)
            mobile_number: Mobile number (optional)
            password_hash: Hashed password (optional)
            auth_provider: Authentication provider (email, google, etc.)

        Returns:
            MongoDBUser object or None if creation failed
        """
        try:
            # Try to get existing user
            user = UserService.get_user_by_firebase_uid(firebase_uid)
            if user:
                # If user exists and we have new data, update it
                update_needed = False
                update_data = {}

                if mobile_number and (not user.mobile_number or user.mobile_number != mobile_number):
                    update_data["mobile_number"] = mobile_number
                    update_needed = True

                if password_hash and (not user.password_hash or user.password_hash != password_hash):
                    update_data["password_hash"] = password_hash
                    update_needed = True

                # Update auth provider if it's different
                if auth_provider and auth_provider != user.auth_provider:
                    update_data["auth_provider"] = auth_provider
                    update_needed = True

                if update_needed:
                    # Get MongoDB database
                    db = get_db()
                    users_collection = db["users"]

                    # Add updated timestamp
                    update_data["updated_at"] = datetime.utcnow()

                    # Update user
                    users_collection.update_one(
                        {"firebase_uid": firebase_uid},
                        {"$set": update_data}
                    )

                    # Refresh user object with updated data
                    user = UserService.get_user_by_firebase_uid(firebase_uid)

                return user

            # User not found, get Firebase user data
            firebase_user = get_firebase_user(firebase_uid)
            if not firebase_user:
                logger.error(f"Firebase user {firebase_uid} not found")
                return None

            # Create new user
            if not username:
                # Generate username from email if not provided
                email = firebase_user.get("email")
                if email:
                    username = email.split("@")[0]
                else:
                    username = f"user_{firebase_uid[:8]}"

            # Determine if email is verified
            email_verified = firebase_user.get("email_verified", False)

            # Create user in MongoDB
            return UserService.create_user(
                firebase_uid=firebase_uid,
                username=username,
                email=firebase_user.get("email"),
                role="student",  # Default role
                display_name=firebase_user.get("display_name"),
                mobile_number=mobile_number,
                password_hash=password_hash,
                auth_provider=auth_provider,
                email_verified=email_verified
            )

        except Exception as e:
            logger.error(f"Error getting or creating user from Firebase: {str(e)}")
            return None

    @staticmethod
    def update_user_login(firebase_uid: str, login_time: datetime, client_ip: str = None) -> bool:
        """
        Update user login information in MongoDB

        Args:
            firebase_uid: Firebase UID
            login_time: Login timestamp
            client_ip: Client IP address (optional)

        Returns:
            True if update was successful, False otherwise
        """
        try:
            # Get MongoDB database
            db = get_db()
            users_collection = db["users"]

            # Find user by Firebase UID
            user = users_collection.find_one({"firebase_uid": firebase_uid})
            if not user:
                logger.error(f"User with Firebase UID {firebase_uid} not found")
                return False

            # Update login information
            update_data = {
                "last_login": login_time,
                "updated_at": datetime.utcnow(),
                "$inc": {"login_count": 1}  # Increment login count
            }

            if client_ip:
                update_data["last_login_ip"] = client_ip

            # Update user
            result = users_collection.update_one(
                {"firebase_uid": firebase_uid},
                update_data
            )

            if result.modified_count > 0:
                logger.info(f"Updated login information for user with Firebase UID {firebase_uid}")
                return True
            else:
                logger.warning(f"No changes made to login information for user with Firebase UID {firebase_uid}")
                return False

        except Exception as e:
            logger.error(f"Error updating user login information: {str(e)}")
            return False