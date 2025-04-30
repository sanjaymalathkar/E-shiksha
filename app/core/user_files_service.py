import logging
from typing import Dict, List, Any, Optional, BinaryIO
from datetime import datetime
from bson.objectid import ObjectId

from app.core.mongodb import get_db, get_gridfs, get_user_files
from app.core.firebase_auth import get_firebase_user
from app.models.mongodb_models import UserFile, UserFileCreate

# Set up logging
logger = logging.getLogger(__name__)

class UserFilesService:
    """Service for managing user files in MongoDB"""
    
    @staticmethod
    def create_user_file(user_id: str, file_data: bytes, file_create: UserFileCreate) -> Optional[UserFile]:
        """
        Create a new user file in MongoDB
        
        Args:
            user_id: Firebase UID of the user
            file_data: Binary file data
            file_create: File creation data
        
        Returns:
            Created UserFile object or None if creation failed
        """
        try:
            # Get GridFS instance
            fs = get_gridfs()
            
            # Prepare metadata
            metadata = {
                "user_id": user_id,
                "exam_type": file_create.exam_type,
                "tags": file_create.tags,
                **file_create.metadata
            }
            
            # Save file to GridFS
            file_id = fs.put(
                file_data,
                filename=file_create.filename,
                content_type=file_create.content_type,
                metadata=metadata
            )
            
            # Get the saved file
            grid_out = fs.get(file_id)
            
            # Create UserFile object
            user_file = UserFile(
                file_id=str(file_id),
                user_id=user_id,
                filename=grid_out.filename,
                content_type=grid_out.content_type,
                size=grid_out.length,
                upload_date=grid_out.upload_date,
                exam_type=file_create.exam_type,
                tags=file_create.tags,
                metadata=file_create.metadata
            )
            
            return user_file
        
        except Exception as e:
            logger.error(f"Error creating user file: {str(e)}")
            return None
    
    @staticmethod
    def get_user_file(file_id: str, user_id: str = None) -> Optional[UserFile]:
        """
        Get a user file by ID
        
        Args:
            file_id: ID of the file
            user_id: Firebase UID of the user (for access control)
        
        Returns:
            UserFile object or None if file not found or access denied
        """
        try:
            # Get GridFS instance
            fs = get_gridfs()
            
            # Get file
            grid_out = fs.get(ObjectId(file_id))
            
            # Check if user has access to this file
            if user_id and grid_out.metadata.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to access file {file_id} belonging to another user")
                return None
            
            # Create UserFile object
            user_file = UserFile(
                file_id=str(grid_out._id),
                user_id=grid_out.metadata.get("user_id"),
                filename=grid_out.filename,
                content_type=grid_out.content_type,
                size=grid_out.length,
                upload_date=grid_out.upload_date,
                exam_type=grid_out.metadata.get("exam_type"),
                tags=grid_out.metadata.get("tags", []),
                metadata=grid_out.metadata
            )
            
            return user_file
        
        except Exception as e:
            logger.error(f"Error getting user file {file_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_file_data(file_id: str, user_id: str = None) -> Optional[bytes]:
        """
        Get file data by ID
        
        Args:
            file_id: ID of the file
            user_id: Firebase UID of the user (for access control)
        
        Returns:
            File data as bytes or None if file not found or access denied
        """
        try:
            # Get GridFS instance
            fs = get_gridfs()
            
            # Get file
            grid_out = fs.get(ObjectId(file_id))
            
            # Check if user has access to this file
            if user_id and grid_out.metadata.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to access file {file_id} belonging to another user")
                return None
            
            # Return file data
            return grid_out.read()
        
        except Exception as e:
            logger.error(f"Error getting file data {file_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_user_files(user_id: str, exam_type: str = None, tags: List[str] = None) -> List[UserFile]:
        """
        Get all files for a specific user
        
        Args:
            user_id: Firebase UID of the user
            exam_type: Filter by exam type (optional)
            tags: Filter by tags (optional)
        
        Returns:
            List of UserFile objects
        """
        try:
            # Get GridFS instance
            fs = get_gridfs()
            
            # Build query
            query = {"metadata.user_id": user_id}
            
            if exam_type:
                query["metadata.exam_type"] = exam_type
            
            if tags:
                query["metadata.tags"] = {"$all": tags}
            
            # Find all files matching the query
            files = []
            for grid_out in fs.find(query):
                files.append(UserFile(
                    file_id=str(grid_out._id),
                    user_id=grid_out.metadata.get("user_id"),
                    filename=grid_out.filename,
                    content_type=grid_out.content_type,
                    size=grid_out.length,
                    upload_date=grid_out.upload_date,
                    exam_type=grid_out.metadata.get("exam_type"),
                    tags=grid_out.metadata.get("tags", []),
                    metadata=grid_out.metadata
                ))
            
            return files
        
        except Exception as e:
            logger.error(f"Error getting user files for user {user_id}: {str(e)}")
            return []
    
    @staticmethod
    def delete_user_file(file_id: str, user_id: str) -> bool:
        """
        Delete a user file
        
        Args:
            file_id: ID of the file to delete
            user_id: Firebase UID of the user (for access control)
        
        Returns:
            True if file was deleted, False otherwise
        """
        try:
            # Get GridFS instance
            fs = get_gridfs()
            
            # Get file to check ownership
            grid_out = fs.get(ObjectId(file_id))
            
            # Check if user has access to this file
            if grid_out.metadata.get("user_id") != user_id:
                logger.warning(f"User {user_id} attempted to delete file {file_id} belonging to another user")
                return False
            
            # Delete file
            fs.delete(ObjectId(file_id))
            return True
        
        except Exception as e:
            logger.error(f"Error deleting user file {file_id}: {str(e)}")
            return False
