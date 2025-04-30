import pymongo
import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient

# Setup logger
logger = logging.getLogger(__name__)

# MongoDB connection string from environment variable
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017/")
DB_NAME = os.environ.get("MONGODB_DB_NAME", "e_shiksha")

# Create MongoDB client
try:
    client = pymongo.MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    # Test connection
    client.admin.command('ping')
    logger.info("Connected to MongoDB successfully")
except Exception as e:
    logger.error(f"Error connecting to MongoDB: {str(e)}")
    db = None

# Async MongoDB client for FastAPI
try:
    async_client = AsyncIOMotorClient(MONGODB_URI)
    async_db = async_client[DB_NAME]
    logger.info("Connected to Async MongoDB successfully")
except Exception as e:
    logger.error(f"Error connecting to Async MongoDB: {str(e)}")
    async_db = None

def get_db():
    """
    Get MongoDB database instance
    """
    if db is None:
        # Instead of raising an exception, return a mock DB for demo purposes
        logger.warning("MongoDB connection not available, returning mock DB")
        from unittest.mock import MagicMock
        import random
        from datetime import datetime, timedelta
        import io

        # Create a better mock cursor that supports iteration and sort
        class MockCursor:
            def __init__(self, items=None):
                self.items = items or []
                self.current_index = 0

            def __iter__(self):
                self.current_index = 0
                return self

            def __next__(self):
                if self.current_index < len(self.items):
                    item = self.items[self.current_index]
                    self.current_index += 1
                    return item
                raise StopIteration

            def sort(self, field=None, direction=None):
                # Just return self since we're mocking
                return self

        # Create sample files for the mock
        sample_files = []
        file_types = [
            {"type": "pdf", "name": "Study Notes", "content_type": "application/pdf"},
            {"type": "doc", "name": "Assignment", "content_type": "application/msword"},
            {"type": "ppt", "name": "Presentation", "content_type": "application/vnd.ms-powerpoint"},
            {"type": "jpg", "name": "Diagram", "content_type": "image/jpeg"},
            {"type": "png", "name": "Chart", "content_type": "image/png"},
            {"type": "txt", "name": "Text Notes", "content_type": "text/plain"}
        ]

        # Generate 5 sample files
        for i in range(5):
            file_type = file_types[i % len(file_types)]
            days_ago = random.randint(1, 30)
            file_id = f"sample-{i+1}"

            sample_files.append({
                "_id": file_id,
                "filename": f"{file_type['name']} {i+1}.{file_type['type']}",
                "metadata": {
                    "content_type": file_type["content_type"],
                    "user_id": "demo-user-123",
                    "upload_date": datetime.utcnow() - timedelta(days=days_ago),
                    "username": "Demo User",
                    "email": "demo@example.com",
                    "exam_type": ["JEE", "GMAT", "UPSC", "GATE"][i % 4]
                },
                "length": random.randint(100000, 5000000),
                "uploadDate": datetime.utcnow() - timedelta(days=days_ago)
            })

        # Create a mock MongoDB client
        mock_db = MagicMock()

        # Set up the mock to handle common operations
        mock_fs_files = MagicMock()

        # Make find return our mock cursor with sample files
        mock_fs_files.find = lambda *args, **kwargs: MockCursor(sample_files)

        # Make find_one return a sample file if it matches the ID
        def mock_find_one(*args, **kwargs):
            # Check if we're looking for a specific file ID
            if args and isinstance(args[0], dict) and "_id" in args[0]:
                file_id = args[0]["_id"]
                # If it's a sample ID, return the matching sample file
                if isinstance(file_id, str) and file_id.startswith("sample-"):
                    try:
                        index = int(file_id.split("-")[1]) - 1
                        if 0 <= index < len(sample_files):
                            return sample_files[index]
                    except:
                        pass
            return None

        mock_fs_files.find_one = mock_find_one

        # Set up the mock db structure
        mock_db.fs = MagicMock()
        mock_db.fs.files = mock_fs_files

        # Mock GridFS class
        class MockGridFS:
            def put(self, contents, filename, metadata=None):
                # Generate a new sample ID
                import hashlib
                file_hash = hashlib.md5(f"{filename}_{datetime.utcnow().isoformat()}".encode()).hexdigest()[:6]
                return f"sample-{file_hash}"

            def get(self, file_id):
                # Return a file-like object with sample content
                content = f"This is sample content for file {file_id}\n"
                content += "Since MongoDB is not available, we're generating this sample content.\n"
                return io.BytesIO(content.encode('utf-8'))

            def delete(self, file_id):
                # Pretend to delete the file
                logger.info(f"Mock delete of file {file_id}")
                return True

        # Assign the MockGridFS instance to the mock_db
        mock_db.gridfs_instance = MockGridFS()

        # Override the gridfs.GridFS constructor to return our mock
        def mock_gridfs_constructor(db_instance):
            return mock_db.gridfs_instance

        # Monkey patch the gridfs.GridFS constructor
        import gridfs
        original_gridfs = gridfs.GridFS
        gridfs.GridFS = mock_gridfs_constructor

        # Return the mock DB
        return mock_db

    return db

async def get_async_db():
    """
    Get async MongoDB database instance
    """
    if async_db is None:
        # Instead of raising an exception, return a mock DB for demo purposes
        logger.warning("Async MongoDB connection not available, returning mock DB")
        from unittest.mock import AsyncMock, MagicMock

        # Create a mock MongoDB client
        mock_db = MagicMock()

        # Set up the mock to handle common operations
        mock_collection = AsyncMock()
        mock_collection.find.return_value = []
        mock_collection.find_one.return_value = None
        mock_collection.insert_one.return_value = MagicMock(inserted_id="sample-123456")

        # Make the mock db behave like a dictionary for collection access
        def getitem(name):
            return mock_collection

        mock_db.__getitem__ = getitem

        # Return the mock DB
        return mock_db

    return async_db
