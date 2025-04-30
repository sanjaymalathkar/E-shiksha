import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    """
    Service for sending email notifications to users
    """

    def __init__(self):
        """
        Initialize the email service with configuration from environment variables
        """
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.sender_email = os.getenv("SENDER_EMAIL", "noreply@educationapp.com")
        self.sender_name = os.getenv("SENDER_NAME", "Education App")

        # Check if email service is configured
        self.is_configured = bool(self.smtp_username and self.smtp_password)

        if not self.is_configured:
            logger.warning("Email service not configured. Set SMTP_USERNAME and SMTP_PASSWORD environment variables.")

    def send_email(self, recipient_email: str, subject: str, html_content: str, text_content: Optional[str] = None) -> bool:
        """
        Send an email to a recipient

        Args:
            recipient_email: Email address of the recipient
            subject: Subject of the email
            html_content: HTML content of the email
            text_content: Plain text content of the email (optional)

        Returns:
            True if the email was sent successfully, False otherwise
        """
        # Check if we're in development mode
        dev_mode = os.environ.get("ENVIRONMENT", "development") == "development"

        if not self.is_configured:
            if dev_mode:
                # In development mode, log the email content and pretend it was sent
                logger.warning("Email service not configured. In development mode, logging email content instead of sending.")
                logger.info(f"Would have sent email to: {recipient_email}")
                logger.info(f"Subject: {subject}")
                logger.info(f"HTML Content: {html_content[:200]}...")
                if text_content:
                    logger.info(f"Text Content: {text_content[:200]}...")

                # Save the email to a file for inspection
                try:
                    os.makedirs("data/emails", exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"data/emails/email_{timestamp}.html"

                    with open(filename, "w") as f:
                        f.write(f"To: {recipient_email}\n")
                        f.write(f"Subject: {subject}\n")
                        f.write(f"From: {self.sender_name} <{self.sender_email}>\n")
                        f.write("\n")
                        f.write(html_content)

                    logger.info(f"Email saved to {filename}")
                except Exception as e:
                    logger.error(f"Error saving email to file: {str(e)}")

                # Return True in development mode to simulate successful sending
                return True
            else:
                # In production mode, return False if not configured
                logger.warning("Email service not configured. Email not sent.")
                return False

        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{self.sender_name} <{self.sender_email}>"
            message["To"] = recipient_email

            # Add plain text version (if provided)
            if text_content:
                message.attach(MIMEText(text_content, "plain"))

            # Add HTML version
            message.attach(MIMEText(html_content, "html"))

            # Connect to SMTP server and send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(message)

            logger.info(f"Email sent to {recipient_email}")
            return True

        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")

            if dev_mode:
                # In development mode, save the email to a file even if sending fails
                try:
                    os.makedirs("data/emails", exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"data/emails/email_{timestamp}_failed.html"

                    with open(filename, "w") as f:
                        f.write(f"To: {recipient_email}\n")
                        f.write(f"Subject: {subject}\n")
                        f.write(f"From: {self.sender_name} <{self.sender_email}>\n")
                        f.write(f"Error: {str(e)}\n")
                        f.write("\n")
                        f.write(html_content)

                    logger.info(f"Failed email saved to {filename}")
                except Exception as file_error:
                    logger.error(f"Error saving failed email to file: {str(file_error)}")

            return False

    def send_study_plan_email(self, recipient_email: str, study_plan: Dict[str, Any]) -> bool:
        """
        Send a study plan email to a user

        Args:
            recipient_email: Email address of the recipient
            study_plan: Study plan data

        Returns:
            True if the email was sent successfully, False otherwise
        """
        try:
            # Extract metadata
            metadata = study_plan.get("metadata", {})
            dlc_score = metadata.get("dlc_score", 5)
            topics_per_day = metadata.get("topics_per_day", 3)
            exam_type = metadata.get("exam_type", "General")

            # Get today's plan
            today = datetime.now().strftime("%Y-%m-%d")
            today_plan = None

            for day in study_plan.get("days", []):
                if day.get("date") == today:
                    today_plan = day
                    break

            # If no plan for today, use the first day
            if not today_plan and study_plan.get("days"):
                today_plan = study_plan["days"][0]

            if not today_plan:
                logger.error("No study plan available for today")
                return False

            # Create email subject
            subject = f"Your Daily Study Plan - {today}"

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
                        <h1>Your Daily Study Plan</h1>
                        <p>{today}</p>
                    </div>
                    <div class="content">
                        <p>Hello,</p>
                        <p>Based on your IQ assessment (Learning Capacity Score: <strong>{dlc_score}/10</strong>),
                        here is your personalized study plan for today:</p>

                        <h2>Today's Topics</h2>
            """

            # Add topics
            for topic in today_plan.get("topics", []):
                html_content += f'<div class="topic"><strong>{topic}</strong></div>'

            # Add activities if available
            if today_plan.get("activities"):
                html_content += "<h2>Recommended Activities</h2><ul>"
                for activity in today_plan["activities"]:
                    html_content += f"<li>{activity}</li>"
                html_content += "</ul>"

            # Add tip if available
            if today_plan.get("tip"):
                html_content += f'<div class="tip"><strong>Tip for Today:</strong> {today_plan["tip"]}</div>'

            # Add footer
            html_content += """
                        <p>Happy studying!</p>
                    </div>
                    <div class="footer">
                        <p>This email was sent based on your IQ assessment and learning capacity.</p>
                        <p>© 2023 Education App. All rights reserved.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            # Create plain text content
            text_content = f"""
            Your Daily Study Plan - {today}

            Hello,

            Based on your IQ assessment (Learning Capacity Score: {dlc_score}/10), here is your personalized study plan for today:

            Today's Topics:
            """

            for topic in today_plan.get("topics", []):
                text_content += f"- {topic}\n"

            if today_plan.get("activities"):
                text_content += "\nRecommended Activities:\n"
                for activity in today_plan["activities"]:
                    text_content += f"- {activity}\n"

            if today_plan.get("tip"):
                text_content += f"\nTip for Today: {today_plan['tip']}\n"

            text_content += """
            Happy studying!

            This email was sent based on your IQ assessment and learning capacity.
            © 2023 Education App. All rights reserved.
            """

            # Send email
            return self.send_email(recipient_email, subject, html_content, text_content)

        except Exception as e:
            logger.error(f"Error sending study plan email: {str(e)}")
            return False

# Create a singleton instance
email_service = EmailService()
