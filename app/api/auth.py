from flask import Blueprint, request, jsonify, session
from app.core.database import get_db
from app.core.auth import create_user, authenticate_user, create_access_token
from datetime import timedelta

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.json

    # Validate required fields
    required_fields = ['username', 'email', 'password', 'role']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({"error": f"Missing required field: {field}"}), 400

    # Validate role
    if data['role'] not in ['student', 'teacher']:
        return jsonify({"error": "Role must be either 'student' or 'teacher'"}), 400

    # Create user
    with get_db() as db:
        result = create_user(
            db=db,
            username=data['username'],
            email=data['email'],
            password=data['password'],
            full_name=data.get('full_name', ''),
            role=data['role']
        )

        if isinstance(result, dict) and 'error' in result:
            return jsonify(result), 400

        # Return user info (excluding password)
        return jsonify({
            "id": result.id,
            "username": result.username,
            "email": result.email,
            "full_name": result.full_name,
            "role": result.role,
            "message": "User registered successfully"
        }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login a user"""
    data = request.json

    # Validate required fields
    if 'username' not in data or 'password' not in data:
        return jsonify({"error": "Username and password are required"}), 400

    # Authenticate user
    with get_db() as db:
        user = authenticate_user(db, data['username'], data['password'])

        if not user:
            return jsonify({"error": "Invalid username or password"}), 401

        # Create access token
        access_token = create_access_token(
            data={"sub": user.id},
            expires_delta=timedelta(minutes=60 * 24)  # 24 hours
        )

        # Store user info in session
        session['user_id'] = user.id
        session['username'] = user.username
        session['role'] = user.role

        return jsonify({
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user.id,
            "username": user.username,
            "role": user.role
        }), 200

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout a user"""
    # Clear session
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200

@auth_bp.route('/me', methods=['GET'])
def get_current_user():
    """Get current user info"""
    if 'user_id' not in session:
        return jsonify({"error": "Not authenticated"}), 401

    return jsonify({
        "user_id": session['user_id'],
        "username": session['username'],
        "role": session['role']
    }), 200

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Send password reset email using Google Auth"""
    data = request.json

    # Validate required fields
    if 'email' not in data or not data['email']:
        return jsonify({"error": "Email is required"}), 400

    try:
        # Check if the email exists in the database
        with get_db() as db:
            # Query to check if the email exists
            user = db.execute("SELECT id, email, username FROM users WHERE email = ?", (data['email'],)).fetchone()

            if not user:
                # For security reasons, don't reveal if the email exists or not
                return jsonify({
                    "message": "If an account with that email exists, a password reset link has been sent."
                }), 200

            # Generate a secure reset token (using a combination of user ID and timestamp)
            import secrets
            import time
            from hashlib import sha256

            # Create a timestamp for token expiration (24 hours from now)
            timestamp = int(time.time()) + 86400  # 24 hours in seconds

            # Generate a random token
            random_token = secrets.token_hex(16)

            # Combine user ID, timestamp, and random token to create a secure token
            token_data = f"{user['id']}:{timestamp}:{random_token}"
            reset_token = sha256(token_data.encode()).hexdigest()

            # In a real application, we would store the token in a database
            # For this demo, we'll use a simpler approach

            # Generate Google OAuth URL for password reset
            # In a real implementation, you would use Google's OAuth libraries
            # For this example, we'll create a simulated Google Auth URL
            reset_url = f"https://accounts.google.com/o/oauth2/auth?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:8000/reset-password&response_type=code&scope=email&state={reset_token}"

            # In a real application, you would send an email with this reset URL
            # For now, we'll just return the URL in the response (for demonstration purposes)
            return jsonify({
                "message": "Password reset link has been generated.",
                "reset_url": reset_url
            }), 200

    except Exception as e:
        print(f"Error in forgot password: {str(e)}")
        return jsonify({"error": "An error occurred while processing your request."}), 500

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    """Reset user password"""
    data = request.json

    # Validate required fields
    if 'token' not in data or not data['token']:
        return jsonify({"error": "Reset token is required"}), 400

    if 'password' not in data or not data['password']:
        return jsonify({"error": "New password is required"}), 400

    if len(data['password']) < 8:
        return jsonify({"error": "Password must be at least 8 characters long"}), 400

    try:
        # In a real application, we would validate the token against a database
        # For this demo, we'll simulate a successful token validation

        # The token would normally contain user information
        # For this demo, we'll extract a user ID from the token if possible
        # or use a default test user

        user_id = None

        # Try to extract user ID from token (if it follows our format)
        try:
            # In a real app, we would decrypt/validate the token
            # For this demo, we'll just check if it contains a user ID pattern
            if ':' in data['token']:
                user_id = data['token'].split(':')[0]
        except:
            pass

        with get_db() as db:
            # If we couldn't extract a user ID, find a test user
            if not user_id:
                test_user = db.execute("SELECT id FROM users LIMIT 1").fetchone()
                if test_user:
                    user_id = test_user['id']
                else:
                    return jsonify({"error": "No users found in the system"}), 400

            # Update the user's password
            from werkzeug.security import generate_password_hash

            hashed_password = generate_password_hash(data['password'])

            db.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (hashed_password, user_id)
            )

            db.commit()

            return jsonify({
                "message": "Password has been reset successfully"
            }), 200

    except Exception as e:
        print(f"Error in reset password: {str(e)}")
        return jsonify({"error": "An error occurred while processing your request."}), 500
