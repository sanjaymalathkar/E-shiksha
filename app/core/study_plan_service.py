import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import os
from app.core.mongodb import get_db
from app.core.user_service import UserService
from app.core.email import email_service

# Set up logging
logger = logging.getLogger(__name__)

class StudyPlanService:
    """Service for managing study plans and daily topic emails"""

    @staticmethod
    def get_study_plan(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the study plan for a user

        Args:
            user_id: Firebase UID

        Returns:
            Study plan or None if not found
        """
        try:
            # Get MongoDB database
            db = get_db()

            # Check if MongoDB is available
            if db is None or isinstance(db, dict) or hasattr(db, 'collections'):
                logger.warning("MongoDB not available, using mock study plan")

                # Try to load mock study plan from file
                mock_plan_path = os.path.join("data", "study_plans", "mock_study_plan.json")

                if os.path.exists(mock_plan_path):
                    try:
                        with open(mock_plan_path, "r") as f:
                            mock_plan = json.load(f)

                            # Update the user_id to match the requested user
                            mock_plan["user_id"] = user_id

                            # Update dates to current dates
                            today = datetime.now()
                            for i, day in enumerate(mock_plan.get("plan", {}).get("days", [])):
                                day_date = today + timedelta(days=i)
                                day["date"] = day_date.strftime("%Y-%m-%d")

                            return mock_plan
                    except Exception as file_error:
                        logger.error(f"Error loading mock study plan: {str(file_error)}")

                # If no mock plan file or error loading it, return a hardcoded mock plan
                return {
                    "user_id": user_id,
                    "plan": {
                        "metadata": {
                            "subject": "Mathematics",
                            "level": "Advanced",
                            "duration_days": 30,
                            "created_at": datetime.now().isoformat()
                        },
                        "days": [
                            {
                                "date": datetime.now().strftime("%Y-%m-%d"),
                                "topics": [
                                    "Linear Algebra Fundamentals",
                                    "Matrix Operations",
                                    "Systems of Linear Equations"
                                ],
                                "activities": [
                                    "Solve 5 practice problems on matrix multiplication",
                                    "Watch video lecture on Gaussian elimination",
                                    "Complete quiz on linear systems"
                                ],
                                "tip": "Focus on understanding the geometric interpretation of matrices."
                            },
                            {
                                "date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
                                "topics": [
                                    "Vector Spaces",
                                    "Linear Transformations",
                                    "Eigenvalues and Eigenvectors"
                                ],
                                "activities": [
                                    "Prove 3 properties of vector spaces",
                                    "Compute eigenvalues for 3x3 matrices",
                                    "Visualize linear transformations using online tools"
                                ],
                                "tip": "Eigenvalues are crucial for understanding how transformations stretch or compress space."
                            }
                        ]
                    }
                }

            # If MongoDB is available, query the database
            plans_collection = db["study_plans"]

            # Find study plan
            plan = plans_collection.find_one({"user_id": user_id})

            if not plan:
                logger.warning(f"No study plan found for user {user_id} in database, using mock plan")
                # Return mock plan
                return StudyPlanService.get_mock_study_plan(user_id)

            return plan

        except Exception as e:
            logger.error(f"Error getting study plan for user {user_id}: {str(e)}")
            # Return mock plan on error
            return StudyPlanService.get_mock_study_plan(user_id)

    @staticmethod
    def get_mock_study_plan(user_id: str) -> Dict[str, Any]:
        """
        Get a mock study plan for testing

        Args:
            user_id: Firebase UID

        Returns:
            Mock study plan
        """
        today = datetime.now()

        return {
            "user_id": user_id,
            "plan": {
                "metadata": {
                    "subject": "Mathematics",
                    "level": "Advanced",
                    "duration_days": 30,
                    "created_at": today.isoformat()
                },
                "days": [
                    {
                        "date": today.strftime("%Y-%m-%d"),
                        "topics": [
                            "Linear Algebra Fundamentals",
                            "Matrix Operations",
                            "Systems of Linear Equations"
                        ],
                        "activities": [
                            "Solve 5 practice problems on matrix multiplication",
                            "Watch video lecture on Gaussian elimination",
                            "Complete quiz on linear systems"
                        ],
                        "tip": "Focus on understanding the geometric interpretation of matrices."
                    },
                    {
                        "date": (today + timedelta(days=1)).strftime("%Y-%m-%d"),
                        "topics": [
                            "Vector Spaces",
                            "Linear Transformations",
                            "Eigenvalues and Eigenvectors"
                        ],
                        "activities": [
                            "Prove 3 properties of vector spaces",
                            "Compute eigenvalues for 3x3 matrices",
                            "Visualize linear transformations using online tools"
                        ],
                        "tip": "Eigenvalues are crucial for understanding how transformations stretch or compress space."
                    }
                ]
            }
        }

    @staticmethod
    def get_todays_topics(user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get today's topics for a user

        Args:
            user_id: Firebase UID

        Returns:
            Dictionary with today's topics or None if not found
        """
        try:
            # Get study plan
            plan_data = StudyPlanService.get_study_plan(user_id)

            if not plan_data:
                logger.warning(f"No study plan found for user {user_id}")
                return None

            # Extract plan details
            plan = plan_data.get("plan", {})
            days = plan.get("days", [])

            if not days:
                logger.warning(f"No days found in study plan for user {user_id}")
                return None

            # Get today's date
            today = datetime.now().strftime("%Y-%m-%d")

            # Find today's plan
            today_plan = None
            for day in days:
                if day.get("date") == today:
                    today_plan = day
                    break

            # If no plan for today, use the first day
            if not today_plan and days:
                today_plan = days[0]

            if not today_plan:
                logger.warning(f"No plan found for today for user {user_id}")
                return None

            # Add metadata to today's plan
            metadata = plan.get("metadata", {})
            today_plan["metadata"] = metadata

            return today_plan

        except Exception as e:
            logger.error(f"Error getting today's topics for user {user_id}: {str(e)}")
            return None

    @staticmethod
    async def send_daily_topic_emails() -> int:
        """
        Send daily topic emails to all users with study plans

        Returns:
            Number of emails sent
        """
        try:
            # Get MongoDB database
            db = get_db()
            plans_collection = db["study_plans"]

            # Find all study plans
            plans = list(plans_collection.find({}))

            if not plans:
                logger.info("No study plans found")
                return 0

            # Send emails
            emails_sent = 0

            for plan_data in plans:
                user_id = plan_data.get("user_id")

                if not user_id:
                    continue

                # Get user
                user = UserService.get_user_by_firebase_uid(user_id)

                if not user:
                    logger.warning(f"User {user_id} not found")
                    continue

                # Get today's topics
                today_plan = StudyPlanService.get_todays_topics(user_id)

                if not today_plan:
                    logger.warning(f"No topics for today for user {user_id}")
                    continue

                # Send email
                email_sent = StudyPlanService.send_daily_topic_email(
                    user_email=user.email,
                    user_name=user.display_name or user.username,
                    today_plan=today_plan
                )

                if email_sent:
                    emails_sent += 1

            logger.info(f"Sent {emails_sent} daily topic emails")
            return emails_sent

        except Exception as e:
            logger.error(f"Error sending daily topic emails: {str(e)}")
            return 0

    @staticmethod
    def send_daily_topic_email(user_email: str, user_name: str, today_plan: Dict[str, Any]) -> bool:
        """
        Send a daily topic email to a user

        Args:
            user_email: User's email address
            user_name: User's name
            today_plan: Today's study plan

        Returns:
            True if email was sent successfully, False otherwise
        """
        try:
            # Check if email service is configured
            if not email_service.is_configured:
                logger.warning("Email service not configured")
                return False

            # Extract plan details
            metadata = today_plan.get("metadata", {})
            topics = today_plan.get("topics", [])
            activities = today_plan.get("activities", [])
            tip = today_plan.get("tip", "")

            # Create email subject
            today = datetime.now().strftime("%Y-%m-%d")
            subject = f"Your Daily Study Topics - {today}"

            # Create HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4F46E5; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; }}
                    .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #666; }}
                    .topic {{ background-color: #EEF2FF; padding: 10px; margin-bottom: 10px; border-radius: 5px; }}
                    .tip {{ background-color: #FFFBEB; padding: 15px; margin-top: 20px; border-left: 4px solid #F59E0B; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Your Daily Study Topics</h1>
                        <p>{today}</p>
                    </div>
                    <div class="content">
                        <p>Hello {user_name},</p>
                        <p>Here are your assigned topics for today:</p>

                        <h2>Today's Topics</h2>
            """

            # Add topics
            for topic in topics:
                html_content += f'<div class="topic"><strong>{topic}</strong></div>'

            # Add activities if available
            if activities:
                html_content += "<h2>Recommended Activities</h2><ul>"
                for activity in activities:
                    html_content += f"<li>{activity}</li>"
                html_content += "</ul>"

            # Add tip if available
            if tip:
                html_content += f'<div class="tip"><strong>Tip for Today:</strong> {tip}</div>'

            # Add footer
            html_content += """
                        <p>Happy studying!</p>
                    </div>
                    <div class="footer">
                        <p>This email was sent based on your personalized study plan.</p>
                        <p>© 2023 E-Shiksha. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Create plain text content
            text_content = f"""
            Your Daily Study Topics - {today}

            Hello {user_name},

            Here are your assigned topics for today:

            Today's Topics:
            """

            for topic in topics:
                text_content += f"- {topic}\n"

            if activities:
                text_content += "\nRecommended Activities:\n"
                for activity in activities:
                    text_content += f"- {activity}\n"

            if tip:
                text_content += f"\nTip for Today: {tip}\n"

            text_content += """
            Happy studying!

            This email was sent based on your personalized study plan.
            © 2023 E-Shiksha. All rights reserved.
            """

            # Send email
            return email_service.send_email(user_email, subject, html_content, text_content)

        except Exception as e:
            logger.error(f"Error sending daily topic email to {user_email}: {str(e)}")
            return False
