import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure
from gridfs import GridFS
from bson.objectid import ObjectId
import certifi

# Set up logging
logger = logging.getLogger(__name__)

# MongoDB connection string from environment variable
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGODB_DB_NAME", "e_shiksha")

# MongoDB client instance
_client = None
_db = None
_fs = None

def get_client() -> MongoClient:
    """Get MongoDB client instance"""
    global _client
    if _client is None:
        try:
            # Use TLS/SSL with certifi for secure connections
            _client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
            # Verify connection
            _client.admin.command('ping')
            logger.info("Connected to MongoDB")
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {str(e)}")
            raise
    return _client

def get_db() -> Database:
    """Get MongoDB database instance"""
    global _db
    if _db is None:
        client = get_client()
        _db = client[DB_NAME]
    return _db

def get_gridfs() -> GridFS:
    """Get GridFS instance for file storage"""
    global _fs
    if _fs is None:
        db = get_db()
        _fs = GridFS(db)
    return _fs

def close_connection():
    """Close MongoDB connection"""
    global _client, _db, _fs
    if _client is not None:
        _client.close()
        _client = None
        _db = None
        _fs = None
        logger.info("MongoDB connection closed")

# File operations with GridFS
def save_file(file_data: bytes, filename: str, content_type: str, metadata: Dict[str, Any]) -> str:
    """
    Save a file to GridFS
    
    Args:
        file_data: Binary file data
        filename: Name of the file
        content_type: MIME type of the file
        metadata: Additional metadata for the file
    
    Returns:
        ID of the saved file
    """
    fs = get_gridfs()
    file_id = fs.put(
        file_data,
        filename=filename,
        content_type=content_type,
        metadata=metadata
    )
    return str(file_id)

def get_file(file_id: str) -> Optional[bytes]:
    """
    Get a file from GridFS by ID
    
    Args:
        file_id: ID of the file to retrieve
    
    Returns:
        File data as bytes, or None if file not found
    """
    fs = get_gridfs()
    try:
        grid_out = fs.get(ObjectId(file_id))
        return grid_out.read()
    except Exception as e:
        logger.error(f"Error retrieving file {file_id}: {str(e)}")
        return None

def get_file_metadata(file_id: str) -> Optional[Dict[str, Any]]:
    """
    Get file metadata from GridFS
    
    Args:
        file_id: ID of the file
    
    Returns:
        File metadata as a dictionary, or None if file not found
    """
    fs = get_gridfs()
    try:
        grid_out = fs.get(ObjectId(file_id))
        metadata = {
            "filename": grid_out.filename,
            "content_type": grid_out.content_type,
            "length": grid_out.length,
            "upload_date": grid_out.upload_date,
            "metadata": grid_out.metadata
        }
        return metadata
    except Exception as e:
        logger.error(f"Error retrieving file metadata {file_id}: {str(e)}")
        return None

def delete_file(file_id: str) -> bool:
    """
    Delete a file from GridFS
    
    Args:
        file_id: ID of the file to delete
    
    Returns:
        True if file was deleted, False otherwise
    """
    fs = get_gridfs()
    try:
        fs.delete(ObjectId(file_id))
        return True
    except Exception as e:
        logger.error(f"Error deleting file {file_id}: {str(e)}")
        return False

def get_user_files(user_id: str) -> List[Dict[str, Any]]:
    """
    Get all files for a specific user
    
    Args:
        user_id: User ID (Firebase UID)
    
    Returns:
        List of file metadata dictionaries
    """
    db = get_db()
    fs = get_gridfs()
    
    # Find all files with matching user_id in metadata
    files = []
    for grid_out in fs.find({"metadata.user_id": user_id}):
        files.append({
            "file_id": str(grid_out._id),
            "filename": grid_out.filename,
            "content_type": grid_out.content_type,
            "length": grid_out.length,
            "upload_date": grid_out.upload_date,
            "metadata": grid_out.metadata
        })
    
    return files
