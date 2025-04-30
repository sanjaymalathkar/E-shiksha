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
# For local development, use a local MongoDB instance
# For production, use MongoDB Atlas
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://localhost:27017/e_shiksha"
)
DB_NAME = os.getenv("MONGODB_DB_NAME", "e_shiksha")

# MongoDB client instance
_client = None
_db = None
_fs = None

def get_client() -> Optional[MongoClient]:
    """Get MongoDB client instance"""
    global _client
    if _client is None:
        try:
            # Check if we're using a local MongoDB instance
            if MONGODB_URI.startswith("mongodb://localhost"):
                # For local development, don't use SSL
                _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
                logger.info("Using local MongoDB without SSL")
            else:
                # Use TLS/SSL with certifi for secure connections to remote MongoDB
                _client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
                logger.info("Using remote MongoDB with SSL")

            # Verify connection
            _client.admin.command('ping')
            logger.info("Connected to MongoDB")
        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"MongoDB connection error: {str(e)}")
            return None
    return _client

def get_db() -> Optional[Database]:
    """Get MongoDB database instance"""
    global _db
    if _db is None:
        client = get_client()
        if client is None:
            logger.warning("MongoDB connection not available, returning mock DB")
            return get_mock_db()
        _db = client[DB_NAME]
    return _db

def get_mock_db():
    """Get a mock database for development"""
    logger.warning("Using mock MongoDB database")

    class MockCollection:
        def __init__(self, name):
            self.name = name
            self.data = []

        def find_one(self, query=None):
            # Simple implementation for development
            if not self.data:
                return None
            return self.data[0]

        def find(self, query=None):
            return self.data

        def insert_one(self, document):
            self.data.append(document)
            return type('obj', (object,), {'inserted_id': 1})

        def update_one(self, query, update):
            return type('obj', (object,), {'modified_count': 1})

        def delete_one(self, query):
            return type('obj', (object,), {'deleted_count': 1})

    class MockDB:
        def __init__(self):
            self.collections = {}

        def __getitem__(self, name):
            if name not in self.collections:
                self.collections[name] = MockCollection(name)
            return self.collections[name]

    return MockDB()

def get_gridfs() -> Optional[GridFS]:
    """Get GridFS instance for file storage"""
    global _fs
    if _fs is None:
        db = get_db()
        if db is None or isinstance(db, MockDB):
            logger.warning("MongoDB connection not available, returning mock GridFS")
            return get_mock_gridfs()
        _fs = GridFS(db)
    return _fs

def get_mock_gridfs():
    """Get a mock GridFS for development"""
    logger.warning("Using mock GridFS")

    class MockGridFS:
        def __init__(self):
            self.files = {}
            self.file_counter = 1

        def put(self, data, filename=None, content_type=None, metadata=None):
            file_id = ObjectId()
            self.files[file_id] = {
                "data": data,
                "filename": filename,
                "content_type": content_type,
                "metadata": metadata,
                "length": len(data) if isinstance(data, bytes) else 0,
                "upload_date": datetime.now()
            }
            return file_id

        def get(self, file_id):
            if file_id not in self.files:
                raise Exception(f"File {file_id} not found")

            file_data = self.files[file_id]

            class MockGridOut:
                def __init__(self, data):
                    self._id = file_id
                    self.filename = data["filename"]
                    self.content_type = data["content_type"]
                    self.length = data["length"]
                    self.upload_date = data["upload_date"]
                    self.metadata = data["metadata"]
                    self._data = data["data"]

                def read(self):
                    return self._data

            return MockGridOut(file_data)

        def delete(self, file_id):
            if file_id in self.files:
                del self.files[file_id]

        def find(self, query=None):
            results = []
            for file_id, file_data in self.files.items():
                # Simple query matching for user_id
                if query and "metadata.user_id" in query:
                    user_id = query["metadata.user_id"]
                    if file_data["metadata"] and file_data["metadata"].get("user_id") == user_id:
                        results.append(self.get(file_id))
                else:
                    results.append(self.get(file_id))
            return results

    return MockGridFS()

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
    try:
        fs = get_gridfs()
        if fs is None:
            logger.error("GridFS not available")
            return "mock-file-id"

        file_id = fs.put(
            file_data,
            filename=filename,
            content_type=content_type,
            metadata=metadata
        )
        return str(file_id)
    except Exception as e:
        logger.error(f"Error saving file: {str(e)}")
        return "mock-file-id"

def get_file(file_id: str) -> Optional[bytes]:
    """
    Get a file from GridFS by ID

    Args:
        file_id: ID of the file to retrieve

    Returns:
        File data as bytes, or None if file not found
    """
    try:
        fs = get_gridfs()
        if fs is None:
            logger.error("GridFS not available")
            return b"Mock file content"

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
    try:
        fs = get_gridfs()
        if fs is None:
            logger.error("GridFS not available")
            return {
                "filename": "mock_file.txt",
                "content_type": "text/plain",
                "length": 100,
                "upload_date": datetime.now(),
                "metadata": {"user_id": "mock-user-id"}
            }

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
    try:
        fs = get_gridfs()
        if fs is None:
            logger.error("GridFS not available")
            return True  # Pretend it worked in development

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
    try:
        db = get_db()
        fs = get_gridfs()

        if fs is None:
            logger.error("GridFS not available")
            # Return mock data for development
            return [
                {
                    "file_id": "mock-file-id-1",
                    "filename": "mock_document.pdf",
                    "content_type": "application/pdf",
                    "length": 12345,
                    "upload_date": datetime.now(),
                    "metadata": {"user_id": user_id, "description": "Mock PDF file"}
                },
                {
                    "file_id": "mock-file-id-2",
                    "filename": "mock_image.jpg",
                    "content_type": "image/jpeg",
                    "length": 54321,
                    "upload_date": datetime.now(),
                    "metadata": {"user_id": user_id, "description": "Mock image file"}
                }
            ]

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
    except Exception as e:
        logger.error(f"Error getting user files: {str(e)}")
        return []
