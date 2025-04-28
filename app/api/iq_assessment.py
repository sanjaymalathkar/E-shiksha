import os
import json
import logging
import time
from fastapi import APIRouter, HTTPException, Request, Body
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.core.ollama_local import run_ollama_json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/iq-assessment",
    tags=["iq-assessment"],
    responses={404: {"description": "Not found"}},
)

# Models
class IQQuestion(BaseModel):
    id: int
    type: str  # mcq, short, puzzle
    difficulty: str  # easy, medium, hard
    question: str
    options: Optional[List[str]] = None
    answer: Optional[str] = None
    time_limit: Optional[int] = None  # in seconds

class IQQuizRequest(BaseModel):
    resource_id: str
    topics: Optional[List[str]] = None

class IQQuizResponse(BaseModel):
    status: str
    message: str
    quiz_id: str
    questions: List[IQQuestion]

class IQQuizSubmission(BaseModel):
    quiz_id: str
    answers: Dict[str, Any]
    response_times: Optional[Dict[str, int]] = None  # Question ID to response time in seconds

class IQAssessmentResult(BaseModel):
    status: str
    message: str
    iq_score: int
    learning_capacity: int
    topics_per_day: int
    analysis: str
    strengths: List[str]
    weaknesses: List[str]
    recommended_topics: List[Dict[str, Any]]

# Fallback IQ assessment questions
FALLBACK_IQ_QUESTIONS = [
    {
        "id": 1,
        "type": "mcq",
        "difficulty": "easy",
        "question": "Which number comes next in the sequence: 2, 4, 6, 8, ?",
        "options": ["10", "12", "14", "16"],
        "answer": "10",
        "time_limit": 30
    },
    {
        "id": 2,
        "type": "mcq",
        "difficulty": "medium",
        "question": "If a shirt costs $25 and is discounted by 20%, what is the final price?",
        "options": ["$5", "$15", "$20", "$22.50"],
        "answer": "$20",
        "time_limit": 45
    },
    {
        "id": 3,
        "type": "puzzle",
        "difficulty": "hard",
        "question": "If you rearrange the letters 'CIFAIPC', you would have the name of a(n):",
        "options": ["City", "Animal", "Ocean", "Country"],
        "answer": "Ocean",
        "time_limit": 60
    },
    {
        "id": 4,
        "type": "short",
        "difficulty": "medium",
        "question": "What is the capital of France?",
        "answer": "Paris",
        "time_limit": 20
    },
    {
        "id": 5,
        "type": "mcq",
        "difficulty": "medium",
        "question": "Which of these is NOT a prime number?",
        "options": ["3", "5", "7", "9"],
        "answer": "9",
        "time_limit": 30
    },
    {
        "id": 6,
        "type": "puzzle",
        "difficulty": "hard",
        "question": "I'm tall when I'm young, and I'm short when I'm old. What am I?",
        "options": ["A person", "A tree", "A candle", "A mountain"],
        "answer": "A candle",
        "time_limit": 60
    },
    {
        "id": 7,
        "type": "mcq",
        "difficulty": "easy",
        "question": "How many sides does a hexagon have?",
        "options": ["4", "5", "6", "8"],
        "answer": "6",
        "time_limit": 20
    },
    {
        "id": 8,
        "type": "short",
        "difficulty": "hard",
        "question": "If you have 3 apples and take away 2, how many apples do you have?",
        "answer": "2",
        "time_limit": 30
    },
    {
        "id": 9,
        "type": "mcq",
        "difficulty": "medium",
        "question": "Which planet is known as the Red Planet?",
        "options": ["Venus", "Mars", "Jupiter", "Saturn"],
        "answer": "Mars",
        "time_limit": 25
    },
    {
        "id": 10,
        "type": "puzzle",
        "difficulty": "hard",
        "question": "What can travel around the world while staying in a corner?",
        "options": ["A stamp", "A letter", "An email", "A postcard"],
        "answer": "A stamp",
        "time_limit": 60
    },
    {
        "id": 11,
        "type": "mcq",
        "difficulty": "easy",
        "question": "What is the square root of 64?",
        "options": ["4", "6", "8", "16"],
        "answer": "8",
        "time_limit": 30
    },
    {
        "id": 12,
        "type": "short",
        "difficulty": "medium",
        "question": "If a plane crashes on the border of the US and Canada, where do they bury the survivors?",
        "answer": "Survivors are not buried",
        "time_limit": 45
    },
    {
        "id": 13,
        "type": "mcq",
        "difficulty": "hard",
        "question": "Which of these numbers is a perfect square and a perfect cube?",
        "options": ["1", "4", "9", "64"],
        "answer": "1",
        "time_limit": 60
    },
    {
        "id": 14,
        "type": "puzzle",
        "difficulty": "medium",
        "question": "What has a head and a tail, but no body?",
        "options": ["A snake", "A coin", "A worm", "A tadpole"],
        "answer": "A coin",
        "time_limit": 45
    },
    {
        "id": 15,
        "type": "mcq",
        "difficulty": "easy",
        "question": "How many degrees are in a right angle?",
        "options": ["45", "90", "180", "360"],
        "answer": "90",
        "time_limit": 20
    }
]

@router.post("/generate-quiz", response_model=IQQuizResponse)
async def generate_iq_quiz(
    request: Request,
    quiz_request: IQQuizRequest = Body(...),
):
    """
    Generate an IQ assessment quiz based on the uploaded resource.
    The quiz includes a mix of general knowledge questions, logical reasoning puzzles,
    and subject-specific questions related to the resource content.
    """
    try:
        # Create quizzes folder if it doesn't exist
        quizzes_folder = os.path.join("data", "quizzes")
        os.makedirs(quizzes_folder, exist_ok=True)

        # Generate a unique quiz ID
        quiz_id = f"quiz_{os.urandom(4).hex()}"

        # Get resource analysis if available
        resource_path = os.path.join("data", "resources", quiz_request.resource_id)
        analysis_file = os.path.join(resource_path, "analysis.json")

        resource_content = ""
        resource_topics = quiz_request.topics or []

        if os.path.exists(analysis_file):
            with open(analysis_file, "r", encoding="utf-8") as f:
                analysis = json.load(f)
                resource_content = analysis.get("full_text", "")
                if not resource_topics and "topics" in analysis:
                    resource_topics = analysis["topics"]

        # Generate IQ assessment questions using Ollama
        prompt = f"""
        Generate an IQ assessment quiz with 15 questions to evaluate a student's cognitive abilities and IQ level.

        The quiz should include:
        1. General knowledge questions (multiple choice)
        2. Logical reasoning puzzles
        3. Mathematical problems
        4. Verbal comprehension questions
        5. Pattern recognition questions

        Additionally, include some subject-specific questions related to these topics: {', '.join(resource_topics)}

        For each question:
        - Assign a difficulty level (easy, medium, hard)
        - Specify the question type (mcq, short, puzzle)
        - For multiple choice questions, provide 4 options
        - Include the correct answer
        - Assign a time limit in seconds (20-60 seconds depending on difficulty)

        Format the response as a JSON array of question objects with these fields:
        id, type, difficulty, question, options (for mcq), answer, time_limit

        Resource content excerpt for context:
        {resource_content[:2000]}

        IMPORTANT: Your response must be a valid JSON array that can be parsed directly. Do not include any explanatory text before or after the JSON.
        """

        try:
            # Generate questions using Ollama
            questions = run_ollama_json(prompt, model="llama3")

            # Validate and process the questions
            if isinstance(questions, list) and len(questions) > 0:
                # Ensure all questions have required fields
                processed_questions = []
                for i, q in enumerate(questions):
                    if isinstance(q, dict) and "question" in q:
                        # Ensure required fields
                        q["id"] = q.get("id", i + 1)
                        q["type"] = q.get("type", "mcq").lower()
                        q["difficulty"] = q.get("difficulty", "medium").lower()
                        q["time_limit"] = q.get("time_limit", 30)

                        # Ensure MCQ questions have options
                        if q["type"] == "mcq" and (not q.get("options") or len(q.get("options", [])) < 2):
                            q["options"] = ["Option A", "Option B", "Option C", "Option D"]

                        processed_questions.append(q)

                # Ensure we have at least 15 questions
                if len(processed_questions) < 15:
                    # Add some from our fallback questions
                    remaining = 15 - len(processed_questions)
                    processed_questions.extend(FALLBACK_IQ_QUESTIONS[:remaining])

                # Limit to 15 questions
                processed_questions = processed_questions[:15]

                # Save the quiz
                quiz_file = os.path.join(quizzes_folder, f"{quiz_id}.json")
                with open(quiz_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "quiz_id": quiz_id,
                        "resource_id": quiz_request.resource_id,
                        "topics": resource_topics,
                        "questions": processed_questions,
                        "created_at": time.time()
                    }, f, ensure_ascii=False, indent=2)

                return IQQuizResponse(
                    status="success",
                    message="IQ assessment quiz generated successfully",
                    quiz_id=quiz_id,
                    questions=[IQQuestion(**q) for q in processed_questions]
                )
            else:
                # Fallback to predefined questions
                logger.warning("Invalid response from Ollama, using fallback questions")

                # Save the quiz with fallback questions
                quiz_file = os.path.join(quizzes_folder, f"{quiz_id}.json")
                with open(quiz_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "quiz_id": quiz_id,
                        "resource_id": quiz_request.resource_id,
                        "topics": resource_topics,
                        "questions": FALLBACK_IQ_QUESTIONS,
                        "created_at": time.time()
                    }, f, ensure_ascii=False, indent=2)

                return IQQuizResponse(
                    status="success",
                    message="IQ assessment quiz generated with fallback questions",
                    quiz_id=quiz_id,
                    questions=[IQQuestion(**q) for q in FALLBACK_IQ_QUESTIONS]
                )

        except Exception as e:
            logger.error(f"Error generating questions with Ollama: {str(e)}")

            # Fallback to predefined questions
            quiz_file = os.path.join(quizzes_folder, f"{quiz_id}.json")
            with open(quiz_file, "w", encoding="utf-8") as f:
                json.dump({
                    "quiz_id": quiz_id,
                    "resource_id": quiz_request.resource_id,
                    "topics": resource_topics,
                    "questions": FALLBACK_IQ_QUESTIONS,
                    "created_at": time.time()
                }, f, ensure_ascii=False, indent=2)

            return IQQuizResponse(
                status="success",
                message="IQ assessment quiz generated with fallback questions due to error",
                quiz_id=quiz_id,
                questions=[IQQuestion(**q) for q in FALLBACK_IQ_QUESTIONS]
            )

    except Exception as e:
        logger.error(f"Error generating IQ quiz: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/evaluate", response_model=IQAssessmentResult)
async def evaluate_iq_quiz(
    request: Request,
    submission: IQQuizSubmission = Body(...),
):
    """
    Evaluate the IQ assessment quiz submission and calculate the user's IQ level.
    The IQ level is used to determine the user's learning capacity and assign appropriate topics.
    """
    try:
        # Get the quiz
        quiz_file = os.path.join("data", "quizzes", f"{submission.quiz_id}.json")
        if not os.path.exists(quiz_file):
            raise HTTPException(status_code=404, detail="Quiz not found")

        with open(quiz_file, "r", encoding="utf-8") as f:
            quiz = json.load(f)

        # Get the resource
        resource_id = quiz.get("resource_id")
        resource_file = os.path.join("data", "resources", resource_id, "analysis.json")

        resource_topics = []
        if os.path.exists(resource_file):
            with open(resource_file, "r", encoding="utf-8") as f:
                resource = json.load(f)
                resource_topics = resource.get("topics", [])

        # Calculate score
        questions = quiz.get("questions", [])
        correct_answers = 0
        total_questions = len(questions)
        response_times = submission.response_times or {}

        # Track performance by question type and difficulty
        performance = {
            "type": {"mcq": 0, "short": 0, "puzzle": 0},
            "difficulty": {"easy": 0, "medium": 0, "hard": 0},
            "total": {"mcq": 0, "short": 0, "puzzle": 0, "easy": 0, "medium": 0, "hard": 0}
        }

        # Calculate average response time
        total_response_time = 0
        response_time_count = 0

        for question in questions:
            q_id = str(question["id"])
            q_type = question.get("type", "mcq")
            q_difficulty = question.get("difficulty", "medium")

            # Update totals
            performance["total"][q_type] += 1
            performance["total"][q_difficulty] += 1

            # Check if question was answered
            if q_id in submission.answers:
                user_answer = str(submission.answers[q_id]).strip().lower()
                correct_answer = str(question.get("answer", "")).strip().lower()

                # Check if answer is correct
                if user_answer == correct_answer:
                    correct_answers += 1
                    performance["type"][q_type] += 1
                    performance["difficulty"][q_difficulty] += 1

                # Track response time
                if q_id in response_times:
                    total_response_time += response_times[q_id]
                    response_time_count += 1

        # Calculate IQ score (base 100, adjusted by performance)
        # Formula: Base 100 + (correct_percentage * 50) - (avg_response_time_penalty)
        correct_percentage = correct_answers / total_questions if total_questions > 0 else 0
        avg_response_time = total_response_time / response_time_count if response_time_count > 0 else 30

        # Response time penalty (0-10 points)
        # Faster responses get lower penalty
        response_time_penalty = min(10, max(0, (avg_response_time - 15) / 5))

        # Calculate raw IQ score
        raw_iq_score = 100 + (correct_percentage * 50) - response_time_penalty

        # Adjust based on difficulty performance
        difficulty_bonus = 0
        if performance["total"]["hard"] > 0:
            hard_performance = performance["difficulty"]["hard"] / performance["total"]["hard"]
            difficulty_bonus = hard_performance * 15  # Up to 15 points bonus for hard questions

        # Final IQ score
        iq_score = round(raw_iq_score + difficulty_bonus)

        # Calculate learning capacity (1-10 scale)
        # Map IQ score to learning capacity
        if iq_score < 90:
            learning_capacity = 3
        elif iq_score < 100:
            learning_capacity = 4
        elif iq_score < 110:
            learning_capacity = 5
        elif iq_score < 120:
            learning_capacity = 6
        elif iq_score < 130:
            learning_capacity = 7
        elif iq_score < 140:
            learning_capacity = 8
        else:
            learning_capacity = 9

        # Calculate topics per day based on learning capacity
        if learning_capacity <= 3:
            topics_per_day = 2
        elif learning_capacity <= 5:
            topics_per_day = 3
        elif learning_capacity <= 7:
            topics_per_day = 5
        else:
            topics_per_day = 7

        # Identify strengths and weaknesses
        strengths = []
        weaknesses = []

        # Check performance by question type
        for q_type in ["mcq", "short", "puzzle"]:
            if performance["total"][q_type] > 0:
                type_performance = performance["type"][q_type] / performance["total"][q_type]
                if type_performance >= 0.7:
                    if q_type == "mcq":
                        strengths.append("Multiple choice questions")
                    elif q_type == "short":
                        strengths.append("Short answer questions")
                    elif q_type == "puzzle":
                        strengths.append("Logical reasoning puzzles")
                elif type_performance <= 0.3:
                    if q_type == "mcq":
                        weaknesses.append("Multiple choice questions")
                    elif q_type == "short":
                        weaknesses.append("Short answer questions")
                    elif q_type == "puzzle":
                        weaknesses.append("Logical reasoning puzzles")

        # Check performance by difficulty
        for q_difficulty in ["easy", "medium", "hard"]:
            if performance["total"][q_difficulty] > 0:
                difficulty_performance = performance["difficulty"][q_difficulty] / performance["total"][q_difficulty]
                if difficulty_performance >= 0.7:
                    strengths.append(f"{q_difficulty.capitalize()} difficulty questions")
                elif difficulty_performance <= 0.3:
                    weaknesses.append(f"{q_difficulty.capitalize()} difficulty questions")

        # Ensure we have at least one strength and weakness
        if not strengths:
            strengths.append("General knowledge questions")
        if not weaknesses:
            weaknesses.append("Complex problem-solving")

        # Generate analysis using Ollama
        analysis_prompt = f"""
        Generate a detailed analysis of a student's IQ assessment results.

        Assessment Results:
        - IQ Score: {iq_score}
        - Learning Capacity: {learning_capacity}/10
        - Correct Answers: {correct_answers}/{total_questions}
        - Average Response Time: {round(avg_response_time, 2)} seconds
        - Strengths: {', '.join(strengths)}
        - Weaknesses: {', '.join(weaknesses)}

        Provide a 2-3 paragraph analysis that:
        1. Explains what the IQ score and learning capacity mean
        2. Highlights the student's cognitive strengths and areas for improvement
        3. Recommends learning strategies based on their profile
        4. Explains why they can handle {topics_per_day} topics per day

        Keep the analysis encouraging and constructive.

        Return your response as a JSON object with a single key "analysis" containing the analysis text.
        """

        try:
            analysis_result = run_ollama_json(analysis_prompt, model="llama3")
            analysis = analysis_result.get("analysis", "")
            if not analysis or not isinstance(analysis, str):
                # Fallback analysis
                analysis = generate_fallback_analysis(iq_score, learning_capacity, correct_answers, total_questions, strengths, weaknesses, topics_per_day)
        except Exception as e:
            logger.error(f"Error generating analysis with Ollama: {str(e)}")
            analysis = generate_fallback_analysis(iq_score, learning_capacity, correct_answers, total_questions, strengths, weaknesses, topics_per_day)

        # Assign topics based on IQ level
        recommended_topics = []

        # If we have resource topics, use them
        if resource_topics:
            # Sort topics by complexity (assuming longer topics are more complex)
            sorted_topics = sorted(resource_topics, key=lambda t: len(t))

            # Assign topics based on learning capacity
            if learning_capacity <= 3:
                # Lower IQ: Assign basic topics (first 1/3 of sorted topics)
                topic_count = min(topics_per_day, len(sorted_topics))
                selected_topics = sorted_topics[:max(1, len(sorted_topics) // 3)]
                recommended_topics = [{"topic": t, "difficulty": "basic"} for t in selected_topics[:topic_count]]
            elif learning_capacity <= 6:
                # Medium IQ: Assign mixed topics (middle 1/3 of sorted topics)
                topic_count = min(topics_per_day, len(sorted_topics))
                start_idx = max(0, len(sorted_topics) // 3)
                end_idx = min(len(sorted_topics), 2 * len(sorted_topics) // 3)
                selected_topics = sorted_topics[start_idx:end_idx]
                recommended_topics = [{"topic": t, "difficulty": "intermediate"} for t in selected_topics[:topic_count]]
            else:
                # Higher IQ: Assign advanced topics (last 1/3 of sorted topics)
                topic_count = min(topics_per_day, len(sorted_topics))
                selected_topics = sorted_topics[max(0, 2 * len(sorted_topics) // 3):]
                recommended_topics = [{"topic": t, "difficulty": "advanced"} for t in selected_topics[:topic_count]]

            # If we don't have enough topics, add some from other difficulty levels
            while len(recommended_topics) < topics_per_day and len(sorted_topics) > len(recommended_topics):
                remaining_topics = [t for t in sorted_topics if not any(r["topic"] == t for r in recommended_topics)]
                if remaining_topics:
                    recommended_topics.append({"topic": remaining_topics[0], "difficulty": "mixed"})

        # Save the assessment result
        assessment_folder = os.path.join("data", "assessments")
        os.makedirs(assessment_folder, exist_ok=True)

        assessment_file = os.path.join(assessment_folder, f"{submission.quiz_id}_result.json")
        with open(assessment_file, "w", encoding="utf-8") as f:
            json.dump({
                "quiz_id": submission.quiz_id,
                "resource_id": resource_id,
                "iq_score": iq_score,
                "learning_capacity": learning_capacity,
                "topics_per_day": topics_per_day,
                "correct_answers": correct_answers,
                "total_questions": total_questions,
                "strengths": strengths,
                "weaknesses": weaknesses,
                "recommended_topics": recommended_topics,
                "analysis": analysis,
                "created_at": time.time()
            }, f, ensure_ascii=False, indent=2)

        return IQAssessmentResult(
            status="success",
            message="IQ assessment evaluated successfully",
            iq_score=iq_score,
            learning_capacity=learning_capacity,
            topics_per_day=topics_per_day,
            analysis=analysis,
            strengths=strengths,
            weaknesses=weaknesses,
            recommended_topics=recommended_topics
        )

    except Exception as e:
        logger.error(f"Error evaluating IQ quiz: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def generate_fallback_analysis(iq_score, learning_capacity, correct_answers, total_questions, strengths, weaknesses, topics_per_day):
    """Generate a fallback analysis if Ollama fails"""

    if learning_capacity <= 3:
        return (
            f"Your IQ assessment results indicate a score of {iq_score}, which corresponds to a Learning Capacity Score of {learning_capacity}/10. "
            f"You answered {correct_answers} out of {total_questions} questions correctly. "
            f"Your strengths include {', '.join(strengths)}, while you may benefit from additional practice in {', '.join(weaknesses)}. "
            f"Based on your learning capacity, we recommend studying {topics_per_day} topics per day. "
            f"This focused approach will allow you to thoroughly understand each concept before moving on. "
            f"Consider using techniques like spaced repetition and concept mapping to strengthen your understanding and retention. "
            f"With consistent practice, you can gradually increase your learning capacity over time."
        )
    elif learning_capacity <= 6:
        return (
            f"Your IQ assessment results indicate a score of {iq_score}, which corresponds to a Learning Capacity Score of {learning_capacity}/10. "
            f"You answered {correct_answers} out of {total_questions} questions correctly. "
            f"Your strengths include {', '.join(strengths)}, while you may benefit from additional practice in {', '.join(weaknesses)}. "
            f"Based on your learning capacity, we recommend studying {topics_per_day} topics per day. "
            f"This balanced approach allows you to cover a moderate amount of material while still ensuring thorough understanding. "
            f"Consider using active learning techniques such as teaching concepts to others and creating summary notes. "
            f"Your learning capacity indicates good potential for academic success with consistent effort and effective study strategies."
        )
    else:
        return (
            f"Your IQ assessment results indicate a score of {iq_score}, which corresponds to a high Learning Capacity Score of {learning_capacity}/10. "
            f"You answered {correct_answers} out of {total_questions} questions correctly. "
            f"Your strengths include {', '.join(strengths)}, while you may benefit from additional practice in {', '.join(weaknesses)}. "
            f"Based on your learning capacity, we recommend studying {topics_per_day} topics per day. "
            f"Your high learning capacity allows you to handle more complex material and make connections between different subjects. "
            f"Consider using advanced study techniques like interleaving (mixing different topics) and elaborative interrogation. "
            f"You have excellent potential for academic achievement and can challenge yourself with advanced concepts and problems."
        )
