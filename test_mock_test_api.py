import requests
import json

def test_mock_test_api():
    """
    Test the mock test generation API.
    """
    # Base URL for the API
    base_url = "http://localhost:8000"
    
    # Endpoint for generating mock test questions
    endpoint = "/api/mock-test/generate"
    
    # Parameters for the request
    params = {
        "exam_type": "JEE",
        "difficulty": "medium",
        "count": 5
    }
    
    # Make the request
    try:
        response = requests.get(f"{base_url}{endpoint}", params=params)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Parse the response as JSON
            data = response.json()
            
            # Print the response
            print("Mock Test Questions:")
            print(json.dumps(data, indent=2))
            
            return data
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return None
    
    except Exception as e:
        print(f"Error making request: {str(e)}")
        return None

if __name__ == "__main__":
    print("Testing Mock Test API...")
    test_mock_test_api()
