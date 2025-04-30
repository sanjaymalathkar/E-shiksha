import pymongo
import logging
from datetime import datetime
from passlib.context import CryptContext

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    """Generate a password hash"""
    return pwd_context.hash(password)

def main():
    """Test MongoDB connection and create a user"""
    try:
        # Connect to MongoDB
        client = pymongo.MongoClient("mongodb://localhost:27017/")
        db = client["e_shiksha"]
        
        # Test connection
        client.admin.command('ping')
        logger.info("Connected to MongoDB successfully")
        
        # Get users collection
        users_collection = db["users"]
        
        # Create a test user
        test_user = {
            "firebase_uid": f"test-firebase-uid-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "username": f"test_user_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "email": f"test_user_{datetime.now().strftime('%Y%m%d%H%M%S')}@example.com",
            "display_name": "Test User",
            "mobile_number": "1234567890",
            "password_hash": get_password_hash("test_password"),
            "role": "student",
            "auth_provider": "email",
            "email_verified": False,
            "last_login": datetime.utcnow(),
            "last_login_ip": "127.0.0.1",
            "login_count": 1,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Insert user into MongoDB
        result = users_collection.insert_one(test_user)
        
        if result.inserted_id:
            logger.info(f"Created test user with ID: {result.inserted_id}")
            logger.info(f"Firebase UID: {test_user['firebase_uid']}")
            logger.info(f"Username: {test_user['username']}")
            logger.info(f"Email: {test_user['email']}")
        else:
            logger.error("Failed to create test user")
        
        # List all users in the collection
        logger.info("Listing all users in the collection:")
        for user in users_collection.find():
            logger.info(f"User: {user['username']} (Firebase UID: {user['firebase_uid']})")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
