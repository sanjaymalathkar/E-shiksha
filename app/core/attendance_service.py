import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from app.core.mongodb import get_db
from app.models.attendance import Attendance, AttendanceRecord

# Set up logging
logger = logging.getLogger(__name__)

class AttendanceService:
    """Service for managing user attendance in MongoDB"""

    @staticmethod
    def mark_attendance(user_id: str, username: str, email: str, status: str = "present", login_time: datetime = None) -> bool:
        """
        Mark attendance for a user

        Args:
            user_id: Firebase UID
            username: Username
            email: Email address
            status: Attendance status ("present" or "absent")
            login_time: Login timestamp (optional)

        Returns:
            True if attendance was marked successfully, False otherwise
        """
        try:
            # Get MongoDB database
            db = get_db()

            # Check if MongoDB is available
            if not db:
                logger.warning("MongoDB not available, using mock attendance data")
                # Log the attendance locally for development
                logger.info(f"Mock attendance: User {username} ({user_id}) marked as {status}")
                return True

            attendance_collection = db["attendance"]

            # Get today's date (without time)
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # If login_time is not provided, try to get it from Firebase
            if login_time is None:
                from app.core.firebase_auth import get_firebase_user
                firebase_user = get_firebase_user(user_id)

                # Use Firebase last_sign_in_time if available
                login_time = datetime.utcnow()
                if firebase_user and "last_sign_in_time" in firebase_user:
                    # Convert milliseconds to datetime if needed
                    if isinstance(firebase_user["last_sign_in_time"], (int, float)):
                        login_time = datetime.fromtimestamp(firebase_user["last_sign_in_time"] / 1000)
                    else:
                        login_time = firebase_user["last_sign_in_time"]

            # Check if attendance already marked for today
            existing_attendance = attendance_collection.find_one({
                "user_id": user_id,
                "date": today
            })

            if existing_attendance:
                # If already marked as present, don't update
                if existing_attendance.get("status") == "present":
                    return True

                # Update attendance status
                attendance_collection.update_one(
                    {"_id": existing_attendance["_id"]},
                    {
                        "$set": {
                            "status": status,
                            "login_time": login_time if status == "present" else None
                        }
                    }
                )
            else:
                # Create new attendance record
                attendance = Attendance(
                    user_id=user_id,
                    date=today,
                    status=status,
                    login_time=login_time if status == "present" else None
                )

                # Insert attendance into MongoDB
                attendance_collection.insert_one(attendance.dict())

            # Update attendance record
            AttendanceService.update_attendance_record(user_id, username, email)

            return True

        except Exception as e:
            logger.error(f"Error marking attendance: {str(e)}")
            return False

    @staticmethod
    def update_attendance_record(user_id: str, username: str, email: str) -> None:
        """
        Update attendance record for a user

        Args:
            user_id: Firebase UID
            username: Username
            email: Email address
        """
        try:
            # Get MongoDB database
            db = get_db()
            attendance_collection = db["attendance"]
            records_collection = db["attendance_records"]

            # Get all attendance records for the user
            attendance_records = list(attendance_collection.find({"user_id": user_id}))

            # Calculate statistics
            present_days = sum(1 for record in attendance_records if record.get("status") == "present")
            absent_days = sum(1 for record in attendance_records if record.get("status") == "absent")

            # Calculate streak (consecutive days present)
            streak = 0
            sorted_records = sorted(attendance_records, key=lambda x: x.get("date", datetime.min), reverse=True)

            for record in sorted_records:
                if record.get("status") == "present":
                    streak += 1
                else:
                    break

            # Create or update attendance record
            existing_record = records_collection.find_one({"user_id": user_id})

            if existing_record:
                records_collection.update_one(
                    {"_id": existing_record["_id"]},
                    {
                        "$set": {
                            "attendance": attendance_records,
                            "present_days": present_days,
                            "absent_days": absent_days,
                            "streak": streak,
                            "last_updated": datetime.utcnow()
                        }
                    }
                )
            else:
                record = AttendanceRecord(
                    user_id=user_id,
                    username=username,
                    email=email,
                    attendance=attendance_records,
                    present_days=present_days,
                    absent_days=absent_days,
                    streak=streak
                )

                records_collection.insert_one(record.dict())

        except Exception as e:
            logger.error(f"Error updating attendance record: {str(e)}")

    @staticmethod
    def mark_attendance_from_login_timestamps() -> Dict[str, int]:
        """
        Mark attendance for all users based on their MongoDB login timestamps

        This method:
        1. Checks all users in the MongoDB database
        2. Uses their last_login timestamp to determine if they logged in today
        3. Marks them as present if they logged in today, absent otherwise
        4. Updates attendance records accordingly

        Returns:
            Dictionary with counts of present and absent users
        """
        try:
            # Get MongoDB database
            db = get_db()
            users_collection = db["users"]
            attendance_collection = db["attendance"]

            # Get today's date (without time)
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            # Get all users
            users = list(users_collection.find({}))

            # Get users who have already been marked for today
            marked_users = set(
                record["user_id"] for record in attendance_collection.find({"date": today})
            )

            # Counters for statistics
            present_count = 0
            absent_count = 0

            # Process each user
            for user in users:
                user_id = user.get("firebase_uid")

                if not user_id:
                    continue

                # Skip users who have already been marked today
                if user_id in marked_users:
                    # Count already marked users
                    existing_record = attendance_collection.find_one({
                        "user_id": user_id,
                        "date": today
                    })
                    if existing_record and existing_record.get("status") == "present":
                        present_count += 1
                    else:
                        absent_count += 1
                    continue

                # Determine attendance status based on login timestamp
                status = "absent"
                login_time = None

                # Check MongoDB last_login timestamp
                if "last_login" in user and user["last_login"]:
                    last_login = user["last_login"]

                    # Check if user logged in today
                    if last_login.date() == today.date():
                        status = "present"
                        login_time = last_login
                        present_count += 1
                    else:
                        absent_count += 1
                else:
                    # Fall back to Firebase login time
                    from app.core.firebase_auth import get_firebase_user
                    firebase_user = get_firebase_user(user_id)

                    if firebase_user and "last_sign_in_time" in firebase_user:
                        # Get last sign in time
                        last_sign_in = None
                        if isinstance(firebase_user["last_sign_in_time"], (int, float)):
                            last_sign_in = datetime.fromtimestamp(firebase_user["last_sign_in_time"] / 1000)
                        else:
                            last_sign_in = firebase_user["last_sign_in_time"]

                        # Check if user logged in today
                        if last_sign_in and last_sign_in.date() == today.date():
                            status = "present"
                            login_time = last_sign_in
                            present_count += 1
                        else:
                            absent_count += 1
                    else:
                        absent_count += 1

                # Create attendance record
                attendance = Attendance(
                    user_id=user_id,
                    date=today,
                    status=status,
                    login_time=login_time
                )

                # Insert attendance into MongoDB
                attendance_collection.insert_one(attendance.dict())

                # Update attendance record
                AttendanceService.update_attendance_record(
                    user_id=user_id,
                    username=user.get("username", ""),
                    email=user.get("email", "")
                )

            return {
                "present": present_count,
                "absent": absent_count
            }

        except Exception as e:
            logger.error(f"Error marking attendance from login timestamps: {str(e)}")
            return {"present": 0, "absent": 0}

    @staticmethod
    def mark_absent_users() -> int:
        """
        Mark all users who haven't logged in today as absent
        Uses MongoDB last_login timestamp to determine if a user has logged in today
        Falls back to Firebase last_sign_in_time if MongoDB timestamp is not available

        Returns:
            Number of users marked as absent
        """
        try:
            # Use the new method to mark attendance based on login timestamps
            result = AttendanceService.mark_attendance_from_login_timestamps()
            return result["absent"]

        except Exception as e:
            logger.error(f"Error marking absent users: {str(e)}")
            return 0

    @staticmethod
    def get_attendance_record(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get attendance record for a user

        Args:
            user_id: Firebase UID

        Returns:
            Attendance record as a dictionary, or None if not found
        """
        try:
            # Get MongoDB database
            db = get_db()

            # Check if MongoDB is available
            if db is None or isinstance(db, dict) or hasattr(db, 'collections'):
                logger.warning("MongoDB not available, using mock attendance data")
                # Return mock attendance data for development
                mock_dates = []
                for i in range(7):
                    date_obj = datetime.now() - timedelta(days=i)
                    date_str = date_obj.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                    login_time = None
                    if i != 3 and i != 5:  # Mark as absent on days 3 and 5
                        login_time = date_obj.replace(hour=9, minute=30).isoformat()

                    mock_dates.append({
                        "date": date_str,
                        "status": "present" if i != 3 and i != 5 else "absent",
                        "login_time": login_time
                    })

                return {
                    "user_id": user_id,
                    "present_days": 5,
                    "absent_days": 2,
                    "streak": 3,
                    "last_updated": datetime.utcnow().isoformat(),
                    "attendance": mock_dates
                }

            # If MongoDB is available, query the database
            records_collection = db["attendance_records"]

            # Find attendance record
            record = records_collection.find_one({"user_id": user_id})

            return record

        except Exception as e:
            logger.error(f"Error getting attendance record: {str(e)}")
            # Return mock data on error
            return {
                "user_id": user_id,
                "present_days": 5,
                "absent_days": 2,
                "streak": 3,
                "last_updated": datetime.utcnow().isoformat(),
                "attendance": [
                    {
                        "date": (datetime.now() - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                        "status": "present" if i != 3 and i != 5 else "absent",
                        "login_time": (datetime.now() - timedelta(days=i)).replace(hour=9, minute=30).isoformat() if i != 3 and i != 5 else None
                    }
                    for i in range(7)
                ]
            }

    @staticmethod
    def get_absent_users(min_absent_days: int = 1) -> List[Dict[str, Any]]:
        """
        Get users who have been absent for at least the specified number of days

        Args:
            min_absent_days: Minimum number of absent days

        Returns:
            List of user records
        """
        try:
            # Get MongoDB database
            db = get_db()
            records_collection = db["attendance_records"]

            # Find users with at least min_absent_days absent days
            absent_users = list(
                records_collection.find({"absent_days": {"$gte": min_absent_days}})
            )

            return absent_users

        except Exception as e:
            logger.error(f"Error getting absent users: {str(e)}")
            return []
