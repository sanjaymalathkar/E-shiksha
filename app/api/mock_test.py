from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any

router = APIRouter(prefix="/api/mock-test", tags=["mock-test"])

# --- Ollama-based Mock Test Generation ---
from app.core.ollama_local import run_ollama, run_ollama_json

# --- Mock Test Questions Definition (fallback if Ollama fails) ---
MOCK_TEST_QUESTIONS = [
    {"id": 1, "type": "mcq", "difficulty": "easy", "question": "Which number comes next in the sequence: 2, 4, 6, 8, ?", "options": ["10", "12", "14", "16"], "answer": "10"},
    {"id": 2, "type": "short", "difficulty": "easy", "question": "What is the color of the sky on a clear day?", "answer": "blue"},
    {"id": 3, "type": "mcq", "difficulty": "easy", "question": "Which shape has three sides?", "options": ["Circle", "Triangle", "Square", "Rectangle"], "answer": "Triangle"},
    {"id": 4, "type": "mcq", "difficulty": "medium", "question": "If all Bloops are Razzies and all Razzies are Lazzies, are all Bloops definitely Lazzies?", "options": ["Yes", "No", "Cannot Say", "Only sometimes"], "answer": "Yes"},
    {"id": 5, "type": "short", "difficulty": "medium", "question": "Recall and write the last word you read in this instruction.", "answer": None},
    {"id": 6, "type": "puzzle", "difficulty": "medium", "question": "A bat and a ball cost $1.10 in total. The bat costs $1 more than the ball. How much does the ball cost?", "answer": "0.05"},
    {"id": 7, "type": "mcq", "difficulty": "hard", "question": "Which of the following is the odd one out? Apple, Banana, Carrot, Grape", "options": ["Apple", "Banana", "Carrot", "Grape"], "answer": "Carrot"},
    {"id": 8, "type": "puzzle", "difficulty": "hard", "question": "If it takes 5 machines 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?", "answer": "5"},
    {"id": 9, "type": "short", "difficulty": "hard", "question": "What did you have for breakfast today? (memory recall)", "answer": None},
    {"id": 10, "type": "mcq", "difficulty": "medium", "question": "Find the missing letter: C, D, F, G, ?", "options": ["H", "I", "E", "J"], "answer": "E"},
    {"id": 11, "type": "puzzle", "difficulty": "easy", "question": "If you rearrange the letters of 'LISTEN', you get another English word. What is it?", "answer": "SILENT"},
    {"id": 12, "type": "mcq", "difficulty": "hard", "question": "Which figure comes next in the pattern: Square, Triangle, Square, Triangle, ?", "options": ["Square", "Circle", "Triangle", "Rectangle"], "answer": "Square"},
    {"id": 13, "type": "short", "difficulty": "medium", "question": "What is 15% of 200?", "answer": "30"},
    {"id": 14, "type": "puzzle", "difficulty": "easy", "question": "What is the next number in the series: 1, 1, 2, 3, 5, ?", "answer": "8"},
]

# --- Pydantic Models ---
class MockTestQuestion(BaseModel):
    id: int
    type: str
    difficulty: str
    question: str
    options: List[str] = None

class MockTestSubmission(BaseModel):
    answers: Dict[int, Any]

class MockTestEvaluation(BaseModel):
    score: int
    daily_learning_capacity: int
    recommended_topics_per_day: int
    analysis: str

# --- API Endpoints ---
@router.get("/questions", response_model=List[MockTestQuestion])
def get_mock_test_questions(topics: str = None):
    """
    Generate adaptive mock test questions using Ollama locally.
    Questions are designed to assess logical reasoning, problem-solving, comprehension, and memory recall.
    If topics are provided, questions will be focused on those topics.
    """
    # Create a more detailed prompt for generating questions
    prompt = """
    Generate a personalized mock test with 10-15 questions to assess a student's cognitive abilities.

    The test should include:
    1. Logical reasoning questions (pattern recognition, deductive reasoning)
    2. Problem-solving questions (mathematical or situational puzzles)
    3. Comprehension questions (understanding and analyzing information)
    4. Memory recall questions (testing information retention)

    Include a balanced mix of:
    - Easy questions (30%)
    - Medium questions (40%)
    - Hard questions (30%)

    For each question, provide:
    - A unique ID number
    - Question type (mcq, short, puzzle)
    - Difficulty level (easy, medium, hard)
    - The question text
    - For MCQs: an array of 4 options
    - The correct answer

    Format the response as a JSON array of question objects.
    """

    # Add topic focus if provided
    if topics:
        try:
            import json as _json
            topic_list = _json.loads(topics)
            if topic_list:
                topic_str = ', '.join(topic_list)
                prompt += f"\n\nFocus the questions on the following topics extracted from the uploaded content: {topic_str}. Make sure the questions test understanding of these specific topics while still assessing cognitive abilities."
        except Exception as e:
            logger.error(f"Error parsing topics: {e}")

    # Generate questions using Ollama
    try:
        questions = run_ollama_json(prompt, model="llama3")

        # Validate the response
        if isinstance(questions, list) and all('question' in q for q in questions):
            # Ensure all questions have required fields and assign IDs if missing
            for idx, q in enumerate(questions):
                q['id'] = q.get('id', idx+1)
                q['type'] = q.get('type', 'mcq').lower()
                q['difficulty'] = q.get('difficulty', 'medium').lower()

                # Ensure MCQ questions have options
                if q['type'] == 'mcq' and (not q.get('options') or len(q.get('options', [])) < 2):
                    q['options'] = ["Option A", "Option B", "Option C", "Option D"]

            # Limit to 15 questions maximum
            questions = questions[:15]

            # Ensure we have at least 10 questions
            if len(questions) < 10:
                # Add some from our fallback questions
                remaining = 10 - len(questions)
                questions.extend(MOCK_TEST_QUESTIONS[:remaining])

            return [MockTestQuestion(**q) for q in questions]
    except Exception as e:
        logger.error(f"Error generating questions with Ollama: {e}")

    # Fallback to static questions if Ollama fails
    return [MockTestQuestion(**q) for q in MOCK_TEST_QUESTIONS[:12]]

@router.post("/evaluate", response_model=MockTestEvaluation)
def evaluate_mock_test(submission: MockTestSubmission):
    """
    Evaluate the mock test submission using Ollama locally.
    Provides a comprehensive analysis of the student's cognitive abilities,
    assigns a Daily Learning Capacity Score (1-10), and recommends the optimal
    number of topics to study per day based on performance.
    """
    answers = submission.answers

    # Get the questions that were answered (we'll need this for the fallback mechanism)
    answered_questions = {}
    for qid, answer in answers.items():
        # Find the question in our fallback list (for fallback scoring)
        for q in MOCK_TEST_QUESTIONS:
            if q['id'] == int(qid):
                answered_questions[qid] = q
                break

    # Prepare a detailed prompt for Ollama
    answer_str = "\n".join([f"Question {qid}: {ans}" for qid, ans in answers.items()])

    prompt = f"""
    Evaluate the following mock test answers from a student. The test assessed logical reasoning, problem-solving, comprehension, and memory recall abilities.

    Student's answers:
    {answer_str}

    Perform a detailed analysis of the student's cognitive abilities based on these answers. Then provide:

    1. A score (number of correct answers, estimated if you don't know the correct answers)
    2. A Daily Learning Capacity Score on a scale of 1-10, where:
       - 1-3: Can effectively learn 1-2 new concepts per day
       - 4-6: Can effectively learn 3-4 new concepts per day
       - 7-8: Can effectively learn 5-6 new concepts per day
       - 9-10: Can effectively learn 7+ new concepts per day
    3. The recommended number of topics the student should study per day based on their performance
    4. A detailed analysis (2-3 paragraphs) of their cognitive abilities, including:
       - Strengths and weaknesses in logical reasoning, problem-solving, comprehension, and memory recall
       - How their learning capacity affects their optimal study approach
       - Specific recommendations for improving their learning efficiency

    Format your response as a JSON object with these keys: score, daily_learning_capacity, recommended_topics_per_day, analysis
    """

    try:
        # Use Ollama to evaluate the answers
        result = run_ollama_json(prompt, model="llama3")

        # Validate the response
        if all(k in result for k in ("score", "daily_learning_capacity", "recommended_topics_per_day", "analysis")):
            # Ensure values are within expected ranges
            result["score"] = int(result.get("score", 0))
            result["daily_learning_capacity"] = min(10, max(1, int(result.get("daily_learning_capacity", 5))))
            result["recommended_topics_per_day"] = min(10, max(1, int(result.get("recommended_topics_per_day", 3))))

            return MockTestEvaluation(**result)
    except Exception as e:
        logger.error(f"Error evaluating test with Ollama: {e}")

    # Fallback to a more sophisticated scoring mechanism if Ollama fails
    correct_answers = 0
    total_questions = len(answers)

    # Count correct answers for questions we know
    for qid, answer in answers.items():
        if qid in answered_questions and answered_questions[qid].get('answer'):
            correct_answer = str(answered_questions[qid]['answer']).strip().lower()
            student_answer = str(answer).strip().lower()

            if student_answer == correct_answer:
                correct_answers += 1

    # Calculate score
    score = correct_answers

    # Calculate daily learning capacity based on performance
    # Formula: Base of 1 + (correct_percentage * 9) to get a score between 1-10
    if total_questions > 0:
        correct_percentage = correct_answers / total_questions
        daily_learning_capacity = round(1 + (correct_percentage * 9))
    else:
        daily_learning_capacity = 5  # Default mid-range if no questions answered

    # Calculate recommended topics per day based on learning capacity
    if daily_learning_capacity <= 3:
        recommended_topics_per_day = 1
    elif daily_learning_capacity <= 6:
        recommended_topics_per_day = 3
    elif daily_learning_capacity <= 8:
        recommended_topics_per_day = 5
    else:
        recommended_topics_per_day = 7

    # Generate a detailed analysis
    if daily_learning_capacity <= 3:
        analysis = (
            f"Your test results indicate a Daily Learning Capacity Score of {daily_learning_capacity}/10. "
            f"You answered approximately {correct_answers} out of {total_questions} questions correctly. "
            f"Based on your performance, you would benefit from a focused approach to learning, concentrating on {recommended_topics_per_day} topic per day. "
            f"This allows you to thoroughly understand each concept before moving on. "
            f"Consider using techniques like spaced repetition and concept mapping to strengthen your understanding and retention. "
            f"With consistent practice, especially in logical reasoning and problem-solving, you can gradually increase your learning capacity."
        )
    elif daily_learning_capacity <= 6:
        analysis = (
            f"Your test results indicate a Daily Learning Capacity Score of {daily_learning_capacity}/10. "
            f"You answered approximately {correct_answers} out of {total_questions} questions correctly. "
            f"Based on your performance, you can effectively handle {recommended_topics_per_day} topics per day. "
            f"You demonstrate good cognitive abilities with room for growth in certain areas. "
            f"Consider balancing your study sessions between new concepts and review of previously learned material. "
            f"Techniques like active recall and elaborative interrogation may help you strengthen your comprehension and memory recall abilities. "
            f"With a structured study plan that includes regular breaks, you can optimize your learning efficiency."
        )
    else:
        analysis = (
            f"Your test results indicate an excellent Daily Learning Capacity Score of {daily_learning_capacity}/10. "
            f"You answered approximately {correct_answers} out of {total_questions} questions correctly. "
            f"Based on your performance, you can effectively manage {recommended_topics_per_day} topics per day. "
            f"You demonstrate strong cognitive abilities across logical reasoning, problem-solving, comprehension, and memory recall. "
            f"To maximize your learning potential, consider using advanced study techniques like interleaving (mixing different topics) and teaching concepts to others. "
            f"Your high learning capacity allows you to make connections between different subjects and explore topics in greater depth. "
            f"Continue challenging yourself with increasingly complex material to maintain and further develop your cognitive abilities."
        )

    return MockTestEvaluation(
        score=score,
        daily_learning_capacity=daily_learning_capacity,
        recommended_topics_per_day=recommended_topics_per_day,
        analysis=analysis
    )
