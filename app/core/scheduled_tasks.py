import logging
import asyncio
import time
from datetime import datetime, timedelta
from app.core.attendance_service import AttendanceService
from app.core.planner_service import PlannerService
from app.core.study_plan_service import StudyPlanService

# Set up logging
logger = logging.getLogger(__name__)

async def mark_attendance_task():
    """Mark attendance for all users based on their MongoDB login timestamps"""
    try:
        # Mark attendance based on login timestamps
        result = AttendanceService.mark_attendance_from_login_timestamps()
        logger.info(f"Marked {result['present']} users as present and {result['absent']} users as absent")

        # Reassign planners for absent users
        reassigned_count = await PlannerService.reassign_planner_for_absent_users()
        logger.info(f"Reassigned planners for {reassigned_count} users")

    except Exception as e:
        logger.error(f"Error in mark_attendance_task: {str(e)}")

async def send_daily_emails_task():
    """Send daily topic emails to all users with study plans"""
    try:
        # Send daily topic emails
        emails_sent = await StudyPlanService.send_daily_topic_emails()
        logger.info(f"Sent {emails_sent} daily topic emails")

    except Exception as e:
        logger.error(f"Error in send_daily_emails_task: {str(e)}")

async def run_scheduled_tasks():
    """Run scheduled tasks at specified intervals"""
    while True:
        try:
            # Get current time
            now = datetime.now()

            # Calculate time until midnight
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            seconds_until_midnight = (midnight - now).total_seconds()

            # Calculate time until morning (9:00 AM)
            morning = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if morning < now:
                morning = morning + timedelta(days=1)
            seconds_until_morning = (morning - now).total_seconds()

            # Determine which task to run next
            if seconds_until_morning < seconds_until_midnight:
                # Wait until morning to send emails
                logger.info(f"Waiting {seconds_until_morning:.2f} seconds until 9:00 AM to send daily emails")
                await asyncio.sleep(seconds_until_morning)

                # Send daily emails
                logger.info("Sending daily topic emails")
                await send_daily_emails_task()

                # Calculate new time until midnight
                now = datetime.now()
                midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                seconds_until_midnight = (midnight - now).total_seconds()

                # Wait until midnight
                logger.info(f"Waiting {seconds_until_midnight:.2f} seconds until midnight")
                await asyncio.sleep(seconds_until_midnight)
            else:
                # Wait until midnight
                logger.info(f"Waiting {seconds_until_midnight:.2f} seconds until midnight")
                await asyncio.sleep(seconds_until_midnight)

            # Run midnight tasks
            logger.info("Running midnight tasks")
            await mark_attendance_task()

            # Wait a bit to avoid running multiple times if the task completes quickly
            await asyncio.sleep(60)

        except Exception as e:
            logger.error(f"Error in run_scheduled_tasks: {str(e)}")
            await asyncio.sleep(60)  # Wait a bit before retrying
