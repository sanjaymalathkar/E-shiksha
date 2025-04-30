import requests
import logging
import json
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Test the direct user create API endpoint"""
    try:
        # Create a unique test user
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        firebase_uid = f"test-firebase-uid-{timestamp}"
        username = f"test_user_{timestamp}"
        email = f"{username}@example.com"
        password = "test_password"
        
        # Prepare the request data
        data = {
            "firebase_uid": firebase_uid,
            "username": username,
            "email": email,
            "password": password,
            "display_name": "Test User",
            "mobile_number": "1234567890",
            "role": "student",
            "client_ip": "127.0.0.1"
        }
        
        logger.info(f"Sending request to create user: {username}")
        logger.info(f"Request data: {json.dumps(data, indent=2)}")
        
        # Send the request to the API endpoint
        response = requests.post(
            "http://localhost:8000/api/direct-user/create",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        # Check the response
        if response.status_code == 200:
            logger.info(f"User created successfully: {response.json()}")
        else:
            logger.error(f"Failed to create user: {response.status_code} - {response.text}")
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
