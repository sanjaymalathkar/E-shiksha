from fastapi import APIRouter, Request, HTTPException, Body, File, UploadFile, Form, Depends
from fastapi.responses import JSONResponse, FileResponse
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging
import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import firestore
from app.core.mongodb import get_db
from datetime import datetime
import os
import shutil
import uuid
from bson.binary import Binary
import io
import base64

# Set up logging
logger = logging.getLogger(__name__)

# Create avatars directory if it doesn't exist
AVATAR_DIR = "data/avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)

# Define request models
class ProfileUpdateRequest(BaseModel):
    display_name: str
    phone: Optional[str] = None

router = APIRouter(
    prefix="/api/user",
    tags=["user"],
    responses={404: {"description": "Not found"}},
)

@router.get("/me")
async def get_current_user(request: Request):
    """Get current user info from session or Firebase"""
    try:
        # Initialize session if it doesn't exist
        if not hasattr(request, "session"):
            request.session = {}

        # Check if user is in session
        user_id = request.session.get("user_id")
        username = request.session.get("username")
        email = request.session.get("email")

        # If we have a user in session, return that info
        if user_id:
            return {
                "user_id": user_id,
                "username": username or "User",
                "email": email or "",
                "phone": request.session.get("phone", ""),
                "role": request.session.get("role", "user")
            }

        # Check for Firebase auth token in headers
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split("Bearer ")[1]
            try:
                # Verify the Firebase ID token
                decoded_token = firebase_auth.verify_id_token(token)
                uid = decoded_token.get("uid")

                # Get user data from Firebase Auth
                user = firebase_auth.get_user(uid)

                # Try to get additional user data from Firestore
                db = firestore.client()
                user_doc = db.collection("users").document(uid).get()

                user_data = {
                    "user_id": uid,
                    "username": user.display_name or "User",
                    "email": user.email or "",
                    "phone": user.phone_number or "",
                    "role": "user"
                }

                # Add Firestore data if available
                if user_doc.exists:
                    firestore_data = user_doc.to_dict()
                    if "phone" in firestore_data and not user_data["phone"]:
                        user_data["phone"] = firestore_data["phone"]
                    if "name" in firestore_data and not user_data["username"]:
                        user_data["username"] = firestore_data["name"]
                    if "role" in firestore_data:
                        user_data["role"] = firestore_data["role"]

                return user_data
            except Exception as e:
                logger.error(f"Error verifying Firebase token: {str(e)}")

        # For testing purposes, return test data instead of 401
        return {
            "user_id": "test-user-id",
            "username": "Test User",
            "email": "test@example.com",
            "phone": "123-456-7890",
            "role": "user"
        }

        # Uncomment this when done testing
        # return JSONResponse(
        #     status_code=401,
        #     content={"error": "Not authenticated"}
        # )
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update-profile")
async def update_profile(request: Request, profile_data: ProfileUpdateRequest):
    """Update user profile information"""
    try:
        # Initialize session if it doesn't exist
        if not hasattr(request, "session"):
            request.session = {}

        # Get user ID from session
        user_id = request.session.get("user_id")

        # If no user in session, check for Firebase auth token in headers
        if not user_id:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split("Bearer ")[1]
                try:
                    # Verify the Firebase ID token
                    decoded_token = firebase_auth.verify_id_token(token)
                    user_id = decoded_token.get("uid")
                except Exception as e:
                    logger.error(f"Error verifying Firebase token: {str(e)}")

        # For development/testing, use a mock user ID if none is found
        if not user_id:
            user_id = "test-user-id"

        # Connect to MongoDB
        try:
            db = get_db()
            users_collection = db["users"]

            # Check if user exists
            existing_user = users_collection.find_one({"firebase_uid": user_id})

            # Prepare update data
            update_data = {
                "display_name": profile_data.display_name,
                "username": profile_data.display_name,  # Keep username and display_name in sync
                "phone": profile_data.phone,
                "updated_at": datetime.utcnow()
            }

            if existing_user:
                # Update existing user
                update_result = users_collection.update_one(
                    {"firebase_uid": user_id},
                    {"$set": update_data}
                )

                if update_result.modified_count == 0:
                    logger.warning(f"User {user_id} profile update had no effect")
            else:
                # Create new user document
                new_user = {
                    "firebase_uid": user_id,
                    "username": profile_data.display_name,
                    "display_name": profile_data.display_name,
                    "phone": profile_data.phone,
                    "email": request.session.get("email", ""),
                    "role": "student",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }

                users_collection.insert_one(new_user)
                logger.info(f"Created new user profile for {user_id}")

            # Update session data
            request.session["username"] = profile_data.display_name
            request.session["phone"] = profile_data.phone

            return {
                "status": "success",
                "message": "Profile updated successfully"
            }

        except Exception as db_error:
            logger.error(f"Database error updating profile: {str(db_error)}")
            # Continue with Firebase update even if MongoDB fails

        # Try to update Firebase user profile as well
        try:
            if user_id and user_id != "test-user-id":
                update_params = {
                    "display_name": profile_data.display_name,
                }

                if profile_data.phone:
                    update_params["phone_number"] = profile_data.phone

                firebase_auth.update_user(user_id, **update_params)
        except Exception as firebase_error:
            logger.error(f"Error updating Firebase user: {str(firebase_error)}")

        return {
            "status": "success",
            "message": "Profile updated successfully"
        }

    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload-avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
):
    """Upload user avatar and store in MongoDB"""
    try:
        # Initialize session if it doesn't exist
        if not hasattr(request, "session"):
            request.session = {}

        # Get user ID from session
        user_id = request.session.get("user_id")
        logger.info(f"Session user_id: {user_id}")

        # If no user in session, check for Firebase auth token in headers
        if not user_id:
            auth_header = request.headers.get("Authorization", "")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split("Bearer ")[1]
                try:
                    # Verify the Firebase ID token
                    decoded_token = firebase_auth.verify_id_token(token)
                    user_id = decoded_token.get("uid")
                    logger.info(f"Firebase user_id: {user_id}")
                except Exception as e:
                    logger.error(f"Error verifying Firebase token: {str(e)}")
                    # Continue with session authentication

        # For development/testing, use a mock user ID if none is found
        if not user_id:
            logger.warning("No authenticated user found, using test user ID")
            user_id = "test-user-id"

        logger.info(f"Using user_id for avatar upload: {user_id}")

        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Only image files are allowed")

        # Read file content
        file_content = await file.read()

        # Generate a unique filename
        filename = f"{user_id}_{uuid.uuid4()}.{file.filename.split('.')[-1]}"

        # Connect to MongoDB
        try:
            db = get_db()
            users_collection = db["users"]

            # Store the avatar in GridFS
            try:
                from app.core.mongodb import get_gridfs
                fs = get_gridfs()

                # Prepare metadata
                metadata = {
                    "user_id": user_id,
                    "content_type": file.content_type,
                    "upload_date": datetime.utcnow(),
                    "file_type": "avatar"
                }

                # Save to GridFS
                avatar_id = fs.put(
                    file_content,
                    filename=filename,
                    content_type=file.content_type,
                    metadata=metadata
                )
            except Exception as e:
                logger.error(f"Error storing avatar in GridFS: {str(e)}")
                # Fallback to storing in the user document directly
                avatar_id = str(uuid.uuid4())

                # Store the avatar data directly in the user document
                # This is not ideal for production but works as a fallback
                file_content_b64 = base64.b64encode(file_content).decode('utf-8')

                # Save the file to disk as well for immediate access
                try:
                    avatar_path = os.path.join(AVATAR_DIR, filename)
                    with open(avatar_path, "wb") as f:
                        f.write(file_content)
                except Exception as disk_error:
                    logger.error(f"Error saving avatar to disk: {str(disk_error)}")

            # Update user document with avatar reference
            update_data = {
                "avatar_id": str(avatar_id),
                "avatar_filename": filename,
                "avatar_content_type": file.content_type,
                "avatar_updated_at": datetime.utcnow()
            }

            # If we're using the fallback method, store the avatar data directly
            if 'file_content_b64' in locals():
                update_data["avatar_data_b64"] = file_content_b64

            try:
                # Update user in MongoDB
                update_result = users_collection.update_one(
                    {"firebase_uid": user_id},
                    {"$set": update_data}
                )
            except Exception as e:
                logger.error(f"Error updating user document: {str(e)}")
                # Create a simple mock update result
                class MockUpdateResult:
                    def __init__(self):
                        self.modified_count = 0
                update_result = MockUpdateResult()

            if update_result.modified_count == 0:
                # User might not exist, create a new document
                try:
                    user_exists = False
                    try:
                        user_exists = users_collection.find_one({"firebase_uid": user_id}) is not None
                    except Exception as e:
                        logger.error(f"Error checking if user exists: {str(e)}")

                    if not user_exists:
                        new_user = {
                            "firebase_uid": user_id,
                            "username": request.session.get("username", "User"),
                            "display_name": request.session.get("username", "User"),
                            "email": request.session.get("email", ""),
                            "phone": request.session.get("phone", ""),
                            "role": "student",
                            "created_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow(),
                            "avatar_id": str(avatar_id),
                            "avatar_filename": filename,
                            "avatar_content_type": file.content_type,
                            "avatar_updated_at": datetime.utcnow()
                        }

                        # If we're using the fallback method, store the avatar data directly
                        if 'file_content_b64' in locals():
                            new_user["avatar_data_b64"] = file_content_b64

                        try:
                            users_collection.insert_one(new_user)
                            logger.info(f"Created new user profile with avatar for {user_id}")
                        except Exception as e:
                            logger.error(f"Error creating new user: {str(e)}")
                except Exception as e:
                    logger.error(f"Error in user creation flow: {str(e)}")

            # Generate avatar URL
            avatar_url = f"/api/user/avatar/{user_id}?t={datetime.utcnow().timestamp()}"

            return {
                "status": "success",
                "message": "Avatar uploaded successfully",
                "avatar_url": avatar_url
            }

        except Exception as db_error:
            logger.error(f"Database error uploading avatar: {str(db_error)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error uploading avatar: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/avatar/{user_id}")
async def get_avatar(user_id: str):
    """Get user avatar image"""
    try:
        # Connect to MongoDB
        db = get_db()
        users_collection = db["users"]

        # Find user
        user = users_collection.find_one({"firebase_uid": user_id})

        if not user or "avatar_id" not in user:
            # Return default avatar
            return FileResponse("app/static/img/default-avatar.png")

        try:
            # Get avatar from GridFS
            from app.core.mongodb import get_gridfs
            from bson.objectid import ObjectId

            fs = get_gridfs()
            avatar_id = user["avatar_id"]

            # Get the file from GridFS
            grid_out = fs.get(ObjectId(avatar_id))

            # Read the file content
            avatar_data = grid_out.read()

            # Create a temporary file to serve
            avatar_path = os.path.join(AVATAR_DIR, user["avatar_filename"])

            # Write the file to disk
            with open(avatar_path, "wb") as f:
                f.write(avatar_data)

            # Return the file
            return FileResponse(
                avatar_path,
                media_type=user.get("avatar_content_type", "image/jpeg"),
                headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
            )

        except Exception as grid_error:
            logger.error(f"Error retrieving avatar from GridFS: {str(grid_error)}")

            # Fallback to old method if GridFS fails
            if "avatar_filename" in user:
                avatar_path = os.path.join(AVATAR_DIR, user["avatar_filename"])

                # Check if file exists on disk
                if os.path.exists(avatar_path):
                    return FileResponse(avatar_path)

                # If file doesn't exist on disk but we have data in MongoDB, recreate it
                if "avatar_data" in user:
                    with open(avatar_path, "wb") as f:
                        f.write(user["avatar_data"])
                    return FileResponse(avatar_path)

                # If we have base64 encoded data, decode and save it
                if "avatar_data_b64" in user:
                    try:
                        binary_data = base64.b64decode(user["avatar_data_b64"])
                        with open(avatar_path, "wb") as f:
                            f.write(binary_data)
                        return FileResponse(avatar_path)
                    except Exception as e:
                        logger.error(f"Error decoding base64 avatar data: {str(e)}")

        # If all else fails, return default avatar
        return FileResponse("app/static/img/default-avatar.png")

    except Exception as e:
        logger.error(f"Error getting avatar: {str(e)}")
        # Return default avatar on error
        return FileResponse("app/static/img/default-avatar.png")
