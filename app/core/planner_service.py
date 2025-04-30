import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import os
from app.core.mongodb import get_db
from app.core.attendance_service import AttendanceService
from app.core.ollama_local import run_ollama_json

# Set up logging
logger = logging.getLogger(__name__)

class PlannerService:
    """Service for managing study plans based on attendance"""
    
    @staticmethod
    async def reassign_planner_for_absent_users(min_absent_days: int = 1) -> int:
        """
        Reassign study plans for users who have been absent for at least the specified number of days
        
        Args:
            min_absent_days: Minimum number of absent days
            
        Returns:
            Number of users whose plans were reassigned
        """
        try:
            # Get absent users
            absent_users = AttendanceService.get_absent_users(min_absent_days)
            
            if not absent_users:
                logger.info("No absent users found")
                return 0
            
            # Get MongoDB database
            db = get_db()
            plans_collection = db["study_plans"]
            
            # Reassign plans for each absent user
            reassigned_count = 0
            
            for user in absent_users:
                user_id = user.get("user_id")
                
                if not user_id:
                    continue
                
                # Get existing plan
                existing_plan = plans_collection.find_one({"user_id": user_id})
                
                if not existing_plan:
                    logger.info(f"No existing plan found for user {user_id}")
                    continue
                
                # Reassign plan
                new_plan = await PlannerService.reassign_planner(
                    user_id=user_id,
                    absent_days=user.get("absent_days", 0),
                    existing_plan=existing_plan
                )
                
                if new_plan:
                    reassigned_count += 1
            
            return reassigned_count
        
        except Exception as e:
            logger.error(f"Error reassigning planners: {str(e)}")
            return 0
    
    @staticmethod
    async def reassign_planner(user_id: str, absent_days: int, existing_plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Reassign study plan for a user
        
        Args:
            user_id: Firebase UID
            absent_days: Number of days the user has been absent
            existing_plan: Existing study plan
            
        Returns:
            New study plan, or None if reassignment failed
        """
        try:
            # Get MongoDB database
            db = get_db()
            plans_collection = db["study_plans"]
            
            # Extract plan details
            plan_data = existing_plan.get("plan", {})
            metadata = plan_data.get("metadata", {})
            days = plan_data.get("days", [])
            
            if not days:
                logger.warning(f"No days found in existing plan for user {user_id}")
                return None
            
            # Generate new plan using Ollama
            new_plan = await PlannerService.generate_reassigned_plan(
                user_id=user_id,
                absent_days=absent_days,
                existing_plan=plan_data
            )
            
            if not new_plan:
                logger.warning(f"Failed to generate new plan for user {user_id}")
                return None
            
            # Update plan in MongoDB
            plans_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "plan": new_plan,
                        "reassigned_at": datetime.utcnow(),
                        "absent_days": absent_days
                    }
                }
            )
            
            return new_plan
        
        except Exception as e:
            logger.error(f"Error reassigning planner for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    async def generate_reassigned_plan(user_id: str, absent_days: int, existing_plan: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate a reassigned study plan using Ollama
        
        Args:
            user_id: Firebase UID
            absent_days: Number of days the user has been absent
            existing_plan: Existing study plan
            
        Returns:
            New study plan, or None if generation failed
        """
        try:
            # Extract plan details
            metadata = existing_plan.get("metadata", {})
            days = existing_plan.get("days", [])
            
            if not days:
                return None
            
            # Prepare the prompt for Ollama
            prompt = f"""
            Reassign a study plan for a student who has been absent for {absent_days} days.
            
            Student's Learning Profile:
            - Daily Learning Capacity Score (IQ level): {metadata.get("dlc_score", 5)}/10
            - Recommended topics per day: {metadata.get("topics_per_day", 3)}
            - Exam type: {metadata.get("exam_type", "General")}
            
            The student has missed {absent_days} days of their study plan. Please create a new study plan that:
            1. Consolidates the missed material
            2. Adjusts the pace to help the student catch up
            3. Prioritizes the most important topics
            4. Provides additional practice for topics that were missed
            
            Here is the original study plan:
            {json.dumps(existing_plan, indent=2)}
            
            Please provide a new study plan in the same format, but with adjustments to account for the missed days.
            The response should be a valid JSON object with the same structure as the original plan.
            """
            
            # Generate the new plan using Ollama
            result = run_ollama_json(prompt, model="llama3")
            
            # Validate the response
            if not isinstance(result, dict):
                raise ValueError("Invalid response format from Ollama")
            
            # Ensure the plan has the required structure
            if "days" not in result:
                result["days"] = []
            
            # Add metadata if not present
            if "metadata" not in result:
                result["metadata"] = metadata
            
            # Add reassignment info
            result["metadata"]["reassigned"] = True
            result["metadata"]["absent_days"] = absent_days
            result["metadata"]["reassigned_at"] = datetime.now().isoformat()
            
            return result
        
        except Exception as e:
            logger.error(f"Error generating reassigned plan: {str(e)}")
            
            # Fallback to a simple adjustment of the existing plan
            return PlannerService.generate_fallback_reassigned_plan(
                absent_days=absent_days,
                existing_plan=existing_plan
            )
    
    @staticmethod
    def generate_fallback_reassigned_plan(absent_days: int, existing_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a fallback reassigned plan if Ollama fails
        
        Args:
            absent_days: Number of days the user has been absent
            existing_plan: Existing study plan
            
        Returns:
            New study plan
        """
        # Create a copy of the existing plan
        new_plan = existing_plan.copy()
        
        # Extract plan details
        metadata = new_plan.get("metadata", {})
        days = new_plan.get("days", [])
        
        if not days:
            return new_plan
        
        # Add reassignment info
        metadata["reassigned"] = True
        metadata["absent_days"] = absent_days
        metadata["reassigned_at"] = datetime.now().isoformat()
        
        # Simple adjustment: shift the plan by the number of absent days
        # and add a review day at the beginning
        shifted_days = []
        
        # Add a review day at the beginning
        review_day = {
            "day": 1,
            "topics": [],
            "activities": [
                "Review missed material from the past days",
                "Focus on key concepts and fundamentals",
                "Complete practice exercises to reinforce understanding"
            ],
            "tip": "Take your time to catch up on missed material. It's better to understand the concepts well than to rush through them."
        }
        
        # Collect topics from missed days
        missed_topics = []
        for i in range(min(absent_days, len(days))):
            day = days[i]
            missed_topics.extend(day.get("topics", []))
        
        review_day["topics"] = list(set(missed_topics))  # Remove duplicates
        shifted_days.append(review_day)
        
        # Shift the remaining days
        for i in range(len(days)):
            day = days[i].copy()
            day["day"] = i + 2  # +2 because we added a review day at the beginning
            shifted_days.append(day)
        
        new_plan["days"] = shifted_days
        new_plan["metadata"] = metadata
        
        return new_plan
