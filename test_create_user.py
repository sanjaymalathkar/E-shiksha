import pymongo
import datetime
import logging
from passlib.context import CryptContext

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    """Generate a password hash"""
    return pwd_context.hash(password)

# MongoDB connection string
MONGODB_URI = "mongodb://localhost:27017/"
DB_NAME = "e_shiksha"

def create_test_user():
    """Create a test user in MongoDB"""
    try:
        # Connect to MongoDB
        client = pymongo.MongoClient(MONGODB_URI)
        db = client[DB_NAME]
        
        # Test connection
        client.admin.command('ping')
        logger.info("Connected to MongoDB successfully")
        
        # Create a test user
        users_collection = db["users"]
        
        # Generate a unique username and email
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        username = f"test_user_{timestamp}"
        email = f"{username}@example.com"
        firebase_uid = f"test-firebase-uid-{timestamp}"
        
        # Hash the password
        password = "test_password"
        password_hash = get_password_hash(password)
        
        # Create a test user document
        test_user = {
            "firebase_uid": firebase_uid,
            "username": username,
            "email": email,
            "display_name": "Test User",
            "mobile_number": "1234567890",
            "password_hash": password_hash,
            "role": "student",
            "auth_provider": "email",
            "email_verified": False,
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow()
        }
        
        # Insert the test user
        result = users_collection.insert_one(test_user)
        
        if result.inserted_id:
            logger.info(f"Test user created with ID: {result.inserted_id}")
            logger.info(f"Firebase UID: {firebase_uid}")
            logger.info(f"Username: {username}")
            logger.info(f"Email: {email}")
            logger.info(f"Password: {password}")
            
            # Retrieve the test user
            retrieved_user = users_collection.find_one({"_id": result.inserted_id})
            
            if retrieved_user:
                logger.info(f"Retrieved test user: {retrieved_user['username']}")
            else:
                logger.error("Failed to retrieve test user")
        else:
            logger.error("Failed to create test user")
        
        # Close the connection
        client.close()
        
    except Exception as e:
        logger.error(f"Error creating test user: {str(e)}")

if __name__ == "__main__":
    create_test_user()
