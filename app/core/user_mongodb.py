import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from bson.objectid import ObjectId

from app.core.mongodb import get_db

# Set up logging
logger = logging.getLogger(__name__)

def create_user(firebase_uid: str, username: str, email: str, display_name: str = None) -> Optional[str]:
    """
    Create a new user in MongoDB
    
    Args:
        firebase_uid: Firebase UID
        username: Username
        email: Email address
        display_name: Display name (optional)
    
    Returns:
        MongoDB user ID or None if creation failed
    """
    db = get_db()
    users_collection = db["users"]
    
    try:
        # Check if user already exists
        existing_user = users_collection.find_one({"firebase_uid": firebase_uid})
        if existing_user:
            logger.info(f"User with Firebase UID {firebase_uid} already exists")
            return str(existing_user["_id"])
        
        # Create user document
        user_doc = {
            "firebase_uid": firebase_uid,
            "username": username,
            "email": email,
            "display_name": display_name,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert user
        result = users_collection.insert_one(user_doc)
        
        if result.inserted_id:
            logger.info(f"Created user {username} with Firebase UID {firebase_uid}")
            return str(result.inserted_id)
        else:
            logger.error(f"Failed to create user {username} with Firebase UID {firebase_uid}")
            return None
    
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return None

def get_user_by_firebase_uid(firebase_uid: str) -> Optional[Dict[str, Any]]:
    """
    Get a user by Firebase UID
    
    Args:
        firebase_uid: Firebase UID
    
    Returns:
        User document or None if not found
    """
    db = get_db()
    users_collection = db["users"]
    
    try:
        user = users_collection.find_one({"firebase_uid": firebase_uid})
        if user:
            # Convert ObjectId to string for serialization
            user["_id"] = str(user["_id"])
            return user
        return None
    
    except Exception as e:
        logger.error(f"Error getting user by Firebase UID: {str(e)}")
        return None

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    Get a user by username
    
    Args:
        username: Username
    
    Returns:
        User document or None if not found
    """
    db = get_db()
    users_collection = db["users"]
    
    try:
        user = users_collection.find_one({"username": username})
        if user:
            # Convert ObjectId to string for serialization
            user["_id"] = str(user["_id"])
            return user
        return None
    
    except Exception as e:
        logger.error(f"Error getting user by username: {str(e)}")
        return None

def update_user(firebase_uid: str, update_data: Dict[str, Any]) -> bool:
    """
    Update a user document
    
    Args:
        firebase_uid: Firebase UID
        update_data: Data to update
    
    Returns:
        True if update was successful, False otherwise
    """
    db = get_db()
    users_collection = db["users"]
    
    try:
        # Add updated_at timestamp
        update_data["updated_at"] = datetime.utcnow()
        
        # Update user
        result = users_collection.update_one(
            {"firebase_uid": firebase_uid},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    except Exception as e:
        logger.error(f"Error updating user: {str(e)}")
        return False
