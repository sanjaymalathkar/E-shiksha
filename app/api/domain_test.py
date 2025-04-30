from fastapi import APIRouter, HTTPException
import json
import os
import random
from typing import Dict, List, Any
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Load mock questions from JSON file
def load_questions(file_name="mock_questions.json"):
    try:
        file_path = f"app/static/{file_name}"
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                return json.load(f)
        else:
            logger.warning(f"File not found: {file_path}")
            return []
    except Exception as e:
        logger.error(f"Error loading questions from {file_name}: {e}")
        return []

@router.get("/questions/{domain}")
async def get_domain_questions(domain: str):
    """Get questions for a specific domain"""
    domain = domain.upper()
    domain_questions = []

    # Load JEE questions from our custom file if domain is JEE
    if domain == "JEE":
        jee_questions = load_questions("jee_questions.json")
        if jee_questions:
            domain_questions = jee_questions
            logger.info(f"Loaded {len(domain_questions)} JEE questions from jee_questions.json")
        else:
            # Fallback to general mock questions if JEE questions not found
            all_questions = load_questions()
            domain_questions = [q for q in all_questions if q.get("exam") == "JEE"]
            logger.info(f"Fallback: Loaded {len(domain_questions)} JEE questions from mock_questions.json")
    elif domain == "NEET":
        # Load NEET questions from our custom file
        neet_questions = load_questions("neet_questions.json")
        if neet_questions:
            domain_questions = neet_questions
            logger.info(f"Loaded {len(domain_questions)} NEET questions from neet_questions.json")
        else:
            # Fallback to general mock questions if NEET questions not found
            all_questions = load_questions()
            domain_questions = [q for q in all_questions if q.get("exam") == "NEET"]
            logger.info(f"Fallback: Loaded {len(domain_questions)} NEET questions from mock_questions.json")
    elif domain == "KCET":
        # Load KCET questions from our custom file
        kcet_questions = load_questions("kcet_questions.json")
        if kcet_questions:
            domain_questions = kcet_questions
            logger.info(f"Loaded {len(domain_questions)} KCET questions from kcet_questions.json")
        else:
            # Fallback to a mix of JEE and NEET questions if KCET questions not found
            all_questions = load_questions()
            jee_questions = [q for q in all_questions if q.get("exam") == "JEE"]
            neet_questions = [q for q in all_questions if q.get("exam") == "NEET"]
            domain_questions = jee_questions + neet_questions
            logger.info(f"Fallback: Loaded {len(domain_questions)} mixed questions for KCET")
    else:
        # If domain not found, use a mix of all questions
        all_questions = load_questions()
        domain_questions = all_questions

    # If no questions found, return an error
    if not domain_questions:
        logger.warning(f"No questions found for domain: {domain}")
        raise HTTPException(status_code=404, detail=f"No questions found for domain: {domain}")

    # Shuffle and limit to 20 questions
    random.shuffle(domain_questions)
    domain_questions = domain_questions[:20]

    logger.info(f"Returning {len(domain_questions)} questions for domain: {domain}")
    return {"questions": domain_questions}

@router.post("/evaluate")
async def evaluate_test(data: Dict[str, Any]):
    """Evaluate test answers using the correct answer key"""
    user_answers = data.get("answers", {})
    questions = data.get("questions", [])

    if not questions:
        raise HTTPException(status_code=400, detail="No questions provided")

    # Calculate score
    correct_count = 0
    question_results = []

    logger.info(f"Evaluating test with {len(questions)} questions")
    logger.info(f"User provided answers for {len(user_answers)} questions")

    for i, question in enumerate(questions):
        # Use index as question_id if id is not present
        question_id = str(question.get("id", i))
        user_answer = user_answers.get(question_id)
        is_correct = False

        # Log the question being evaluated
        logger.info(f"Evaluating question {question_id}: {question.get('subject', 'Unknown')} - {question.get('question', '')[:30]}...")

        if user_answer is not None and "options" in question and "answer" in question:
            # Get the correct answer based on the question format
            if isinstance(question["answer"], int):
                # For JEE questions format where answer is the index
                if 0 <= question["answer"] < len(question["options"]):
                    correct_option = question["options"][question["answer"]]
                    is_correct = (user_answer == correct_option)
                    logger.info(f"Question {question_id}: User answered '{user_answer}', correct is '{correct_option}' (index {question['answer']})")
                else:
                    logger.warning(f"Invalid answer index {question['answer']} for question {question_id}")
                    correct_option = "Unknown (invalid index)"
            else:
                # For other formats where answer might be the actual option
                correct_option = question["answer"]
                is_correct = (user_answer == correct_option)
                logger.info(f"Question {question_id}: User answered '{user_answer}', correct is '{correct_option}'")

            if is_correct:
                correct_count += 1
                logger.info(f"Question {question_id}: CORRECT")
            else:
                logger.info(f"Question {question_id}: INCORRECT")
        else:
            logger.info(f"Question {question_id}: Not answered or missing required fields")

        # Get the correct answer text for display
        if "options" in question and "answer" in question:
            if isinstance(question["answer"], int):
                if 0 <= question["answer"] < len(question["options"]):
                    correct_answer = question["options"][question["answer"]]
                else:
                    correct_answer = "Unknown (invalid index)"
                    logger.warning(f"Invalid answer index {question['answer']} for question {question_id}")
            else:
                correct_answer = question["answer"]
        else:
            correct_answer = "Unknown"
            logger.warning(f"Question {question_id} missing options or answer")

        # Get explanation if available
        explanation = question.get("explanation", "")
        if not explanation:
            logger.info(f"Question {question_id} has no explanation")

        question_results.append({
            "id": question_id,
            "subject": question.get("subject", ""),
            "is_correct": is_correct,
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "explanation": explanation
        })

    # Calculate percentage
    percentage = round((correct_count / len(questions)) * 100)
    logger.info(f"Test evaluation complete: {correct_count}/{len(questions)} correct ({percentage}%)")

    # Calculate learning capacity based on performance
    if percentage >= 80:
        daily_learning_capacity = 9
    elif percentage >= 60:
        daily_learning_capacity = 7
    elif percentage >= 40:
        daily_learning_capacity = 5
    else:
        daily_learning_capacity = 3

    # Calculate recommended topics per day
    if daily_learning_capacity >= 9:
        recommended_topics_per_day = 7
    elif daily_learning_capacity >= 7:
        recommended_topics_per_day = 5
    elif daily_learning_capacity >= 5:
        recommended_topics_per_day = 3
    else:
        recommended_topics_per_day = 2

    # Calculate IQ level based on performance and time taken
    # We'll use a combination of score and subject-wise performance
    iq_level = calculate_iq_level(percentage, question_results)

    # Generate analysis based on performance
    analysis = generate_performance_analysis(percentage, question_results, iq_level)

    return {
        "score": correct_count,
        "total": len(questions),
        "percentage": percentage,
        "daily_learning_capacity": daily_learning_capacity,
        "recommended_topics_per_day": recommended_topics_per_day,
        "iq_level": iq_level,
        "analysis": analysis,
        "question_results": question_results
    }

def calculate_iq_level(percentage: float, question_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate IQ level based on test performance using a more accurate algorithm"""
    # Base IQ calculation - more accurate formula based on academic performance correlation
    # Research suggests IQ correlates with academic performance, but with a more nuanced curve
    if percentage >= 95:
        # Exceptional performance indicates very high IQ
        base_iq = 130 + (percentage - 95) * 1.0  # Can reach up to 135
    elif percentage >= 85:
        # Strong performance indicates above average IQ
        base_iq = 120 + (percentage - 85) * 1.0  # Range: 120-130
    elif percentage >= 70:
        # Good performance indicates high average to above average IQ
        base_iq = 110 + (percentage - 70) * 0.67  # Range: 110-120
    elif percentage >= 50:
        # Average performance indicates average IQ
        base_iq = 90 + (percentage - 50) * 1.0  # Range: 90-110
    elif percentage >= 30:
        # Below average performance indicates low average IQ
        base_iq = 80 + (percentage - 30) * 0.5  # Range: 80-90
    else:
        # Poor performance indicates below average IQ
        base_iq = 70 + percentage * 0.33  # Range: 70-80

    # Calculate subject-wise performance for adjustment
    subject_stats = {}
    difficulty_factor = 0

    for result in question_results:
        subject = result.get("subject", "General")
        if subject not in subject_stats:
            subject_stats[subject] = {"total": 0, "correct": 0, "difficult_correct": 0}

        subject_stats[subject]["total"] += 1

        # Track correct answers
        if result["is_correct"]:
            subject_stats[subject]["correct"] += 1

            # Consider question difficulty if available
            # For JEE, Physics and Mathematics questions are generally considered more difficult
            if subject in ["Physics", "Mathematics"]:
                subject_stats[subject]["difficult_correct"] += 1
                difficulty_factor += 1

    # Calculate subject-wise percentages
    subject_percentages = {}
    for subject, stats in subject_stats.items():
        subject_percentages[subject] = round((stats["correct"] / stats["total"]) * 100) if stats["total"] > 0 else 0

    # Adjust IQ based on balanced performance across subjects
    if len(subject_percentages) >= 2:
        percentages = list(subject_percentages.values())
        max_diff = max(percentages) - min(percentages)

        if max_diff < 15:  # Very well-balanced performance
            base_iq += 7
            logger.info(f"IQ bonus: +7 for very well-balanced performance across subjects")
        elif max_diff < 25:  # Well-balanced performance
            base_iq += 4
            logger.info(f"IQ bonus: +4 for well-balanced performance across subjects")
        elif max_diff > 50:  # Highly unbalanced performance
            base_iq -= 5
            logger.info(f"IQ penalty: -5 for highly unbalanced performance across subjects")
        elif max_diff > 35:  # Unbalanced performance
            base_iq -= 2
            logger.info(f"IQ penalty: -2 for unbalanced performance across subjects")

    # Adjust for difficulty factor - reward solving difficult questions
    if difficulty_factor >= 5:
        base_iq += 5
        logger.info(f"IQ bonus: +5 for solving {difficulty_factor} difficult questions")
    elif difficulty_factor >= 3:
        base_iq += 3
        logger.info(f"IQ bonus: +3 for solving {difficulty_factor} difficult questions")

    # Ensure IQ stays within reasonable bounds
    base_iq = max(70, min(145, base_iq))

    # Determine IQ category based on standard psychological classifications
    iq_category = ""
    if base_iq >= 130:
        iq_category = "Very Superior"
    elif base_iq >= 120:
        iq_category = "Superior"
    elif base_iq >= 110:
        iq_category = "High Average"
    elif base_iq >= 90:
        iq_category = "Average"
    elif base_iq >= 80:
        iq_category = "Low Average"
    else:
        iq_category = "Below Average"

    # Determine strengths based on subject performance
    strengths = []
    for subject, percentage in subject_percentages.items():
        if percentage >= 75:
            strengths.append(subject)

    # Determine areas for improvement
    improvements = []
    for subject, percentage in subject_percentages.items():
        if percentage < 50:
            improvements.append(subject)

    logger.info(f"Calculated IQ: {round(base_iq)} ({iq_category})")
    logger.info(f"Subject percentages: {subject_percentages}")
    logger.info(f"Strengths: {strengths}")
    logger.info(f"Areas for improvement: {improvements}")

    return {
        "score": round(base_iq),
        "category": iq_category,
        "strengths": strengths,
        "improvements": improvements,
        "subject_percentages": subject_percentages
    }

def generate_performance_analysis(percentage: float, question_results: List[Dict[str, Any]], iq_level: Dict[str, Any] = None) -> str:
    """Generate a performance analysis based on test results"""
    # Count correct answers by subject
    subject_stats = {}
    for result in question_results:
        subject = result.get("subject", "General")
        if subject not in subject_stats:
            subject_stats[subject] = {"total": 0, "correct": 0}

        subject_stats[subject]["total"] += 1
        if result["is_correct"]:
            subject_stats[subject]["correct"] += 1

    # Generate analysis text
    if percentage >= 80:
        performance = "excellent"
    elif percentage >= 60:
        performance = "good"
    elif percentage >= 40:
        performance = "average"
    else:
        performance = "below average"

    analysis = f"Your overall performance was {performance} with a score of {percentage}%.\n\n"

    # Add IQ level analysis if available
    if iq_level:
        analysis += f"Based on your performance, your estimated IQ level is {iq_level['score']} ({iq_level['category']}).\n\n"

        if iq_level['strengths']:
            analysis += "Your strengths are in: " + ", ".join(iq_level['strengths']) + ".\n"

        if iq_level['improvements']:
            analysis += "Areas for improvement: " + ", ".join(iq_level['improvements']) + ".\n\n"

    # Add subject-wise analysis
    analysis += "Subject-wise performance:\n"
    for subject, stats in subject_stats.items():
        subject_percentage = round((stats["correct"] / stats["total"]) * 100) if stats["total"] > 0 else 0
        analysis += f"- {subject}: {stats['correct']}/{stats['total']} ({subject_percentage}%)\n"

    # Add recommendations
    if percentage < 60:
        analysis += "\nRecommendations:\n"
        for subject, stats in subject_stats.items():
            subject_percentage = round((stats["correct"] / stats["total"]) * 100) if stats["total"] > 0 else 0
            if subject_percentage < 50:
                analysis += f"- Focus more on {subject} concepts\n"

    return analysis
