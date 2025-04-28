from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import tempfile
import logging
import json
from datetime import datetime

from app.core.ollama_local import run_ollama, run_ollama_json
from app.core.ocr.document_processor import extract_text_from_file

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/api/mock-test-generator",
    tags=["mock-test-generator"],
    responses={404: {"description": "Not found"}},
)

# Models
class MockTestQuestion(BaseModel):
    id: int
    type: str  # mcq, true_false, short_answer
    question: str
    options: Optional[List[str]] = None
    correct_answer: str
    explanation: Optional[str] = None

class MockTestResponse(BaseModel):
    status: str
    message: str
    questions: List[MockTestQuestion]
    topics: List[str]
    file_name: str

@router.post("/generate", response_model=MockTestResponse)
async def generate_mock_test(
    request: Request,
    file: UploadFile = File(...),
    exam_type: Optional[str] = Form(None)
):
    """
    Generate a mock test based on the uploaded file content using OLLAMA model
    """
    try:
        # Create a temporary directory to store the uploaded file
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save the uploaded file
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Extract text from the file
            extracted_text = extract_text_from_file(file_path)
            
            if not extracted_text:
                raise HTTPException(status_code=400, detail="Could not extract text from the uploaded file")
            
            # Limit text length to avoid token limits
            max_text_length = 6000
            truncated_text = extracted_text[:max_text_length] if len(extracted_text) > max_text_length else extracted_text
            
            # Extract topics from the text
            topics = await extract_topics(truncated_text, exam_type)
            
            # Generate mock test questions using OLLAMA
            questions = await generate_questions(truncated_text, topics, exam_type)
            
            return MockTestResponse(
                status="success",
                message="Mock test generated successfully",
                questions=questions,
                topics=topics,
                file_name=file.filename
            )
    
    except Exception as e:
        logger.error(f"Error generating mock test: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def extract_topics(text: str, exam_type: Optional[str] = None) -> List[str]:
    """
    Extract key topics from the text using OLLAMA
    """
    try:
        context = f" for {exam_type} exam" if exam_type else ""
        
        prompt = f"""
        Extract the main educational topics from the following text{context}.
        Identify 5-8 key concepts, subject areas, or themes that would be relevant for creating a mock test.
        Return the result as a JSON array of strings, with each string being a distinct topic.

        Text:
        {text}
        """
        
        result = run_ollama_json(prompt, model="llama3")
        
        if isinstance(result, list):
            return result[:8]  # Limit to 8 topics
        else:
            logger.warning("Topic extraction did not return a list, using fallback method")
            # Fallback: Extract topics using simple keyword extraction
            import re
            from collections import Counter
            
            # Remove common words and punctuation
            words = re.findall(r'\b[A-Za-z]{4,}\b', text.lower())
            word_counts = Counter(words)
            
            # Remove common English words
            common_words = {'this', 'that', 'with', 'from', 'have', 'they', 'will', 'what', 'when', 'where', 'which', 'their', 'there', 'about'}
            for word in common_words:
                if word in word_counts:
                    del word_counts[word]
            
            # Get the most common words as topics
            topics = [word.title() for word, count in word_counts.most_common(8)]
            return topics
    
    except Exception as e:
        logger.error(f"Error extracting topics: {str(e)}")
        return ["General Knowledge"]  # Fallback topic

async def generate_questions(text: str, topics: List[str], exam_type: Optional[str] = None) -> List[MockTestQuestion]:
    """
    Generate mock test questions based on the text and topics using OLLAMA
    """
    try:
        topics_str = ", ".join(topics)
        context = f" for {exam_type} exam" if exam_type else ""
        
        prompt = f"""
        Generate a comprehensive mock test based on the following text{context}.
        
        Text content:
        {text}
        
        Key topics: {topics_str}
        
        Create 10 questions covering the key topics. Include a mix of:
        - Multiple choice questions (type: "mcq")
        - True/False questions (type: "true_false")
        - Short answer questions (type: "short_answer")
        
        For each question, provide:
        - A unique ID number
        - Question type (mcq, true_false, or short_answer)
        - The question text
        - For MCQs: an array of 4 options
        - For True/False: options should be ["True", "False"]
        - The correct answer
        - A brief explanation of the correct answer
        
        Format the response as a JSON array of question objects.
        Each question object should have these fields: id, type, question, options (for mcq and true_false), correct_answer, explanation
        
        Make sure all questions are directly based on the content provided and cover the key topics.
        """
        
        result = run_ollama_json(prompt, model="llama3")
        
        if isinstance(result, list) and len(result) > 0:
            # Validate and format questions
            questions = []
            for i, q in enumerate(result):
                # Ensure all required fields are present
                if "question" not in q:
                    continue
                
                question = {
                    "id": q.get("id", i + 1),
                    "type": q.get("type", "mcq").lower(),
                    "question": q.get("question", ""),
                    "correct_answer": q.get("correct_answer", ""),
                    "explanation": q.get("explanation", "")
                }
                
                # Handle options based on question type
                if question["type"] == "mcq":
                    question["options"] = q.get("options", ["Option A", "Option B", "Option C", "Option D"])
                elif question["type"] == "true_false":
                    question["options"] = ["True", "False"]
                
                questions.append(MockTestQuestion(**question))
            
            return questions[:10]  # Limit to 10 questions
        else:
            logger.warning("Question generation did not return a valid list")
            # Return a fallback question
            return [
                MockTestQuestion(
                    id=1,
                    type="mcq",
                    question="What is the main topic of the uploaded document?",
                    options=[topics[0] if topics else "General Knowledge", "Science", "Mathematics", "History"],
                    correct_answer=topics[0] if topics else "General Knowledge",
                    explanation="This is the primary topic covered in the document."
                )
            ]
    
    except Exception as e:
        logger.error(f"Error generating questions: {str(e)}")
        return [
            MockTestQuestion(
                id=1,
                type="mcq",
                question="What is the main topic of the uploaded document?",
                options=[topics[0] if topics else "General Knowledge", "Science", "Mathematics", "History"],
                correct_answer=topics[0] if topics else "General Knowledge",
                explanation="This is the primary topic covered in the document."
            )
        ]

@router.post("/evaluate")
async def evaluate_mock_test(
    request: Request,
    answers: Dict[str, Any] = Body(...),
    questions: List[Dict[str, Any]] = Body(...)
):
    """
    Evaluate the mock test answers and provide feedback
    """
    try:
        # Calculate score
        total_questions = len(questions)
        correct_answers = 0
        question_results = []
        
        for q in questions:
            question_id = str(q["id"])
            user_answer = answers.get(question_id, "")
            is_correct = False
            
            # Check if the answer is correct
            if q["type"] == "mcq" or q["type"] == "true_false":
                is_correct = user_answer == q["correct_answer"]
            else:  # short_answer
                # For short answers, check if the correct answer is contained in the user's answer
                is_correct = q["correct_answer"].lower() in user_answer.lower()
            
            if is_correct:
                correct_answers += 1
            
            # Add result for this question
            question_results.append({
                "id": q["id"],
                "is_correct": is_correct,
                "user_answer": user_answer,
                "correct_answer": q["correct_answer"],
                "explanation": q.get("explanation", "")
            })
        
        # Calculate score percentage
        score_percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        
        # Calculate daily learning capacity based on performance
        if score_percentage >= 90:
            daily_learning_capacity = 10
        elif score_percentage >= 80:
            daily_learning_capacity = 8
        elif score_percentage >= 70:
            daily_learning_capacity = 7
        elif score_percentage >= 60:
            daily_learning_capacity = 6
        elif score_percentage >= 50:
            daily_learning_capacity = 5
        elif score_percentage >= 40:
            daily_learning_capacity = 4
        elif score_percentage >= 30:
            daily_learning_capacity = 3
        else:
            daily_learning_capacity = 2
        
        # Calculate recommended topics per day based on learning capacity
        if daily_learning_capacity >= 9:
            recommended_topics_per_day = 7
        elif daily_learning_capacity >= 7:
            recommended_topics_per_day = 5
        elif daily_learning_capacity >= 5:
            recommended_topics_per_day = 3
        else:
            recommended_topics_per_day = 2
        
        # Generate analysis using OLLAMA
        analysis = await generate_analysis(correct_answers, total_questions, daily_learning_capacity)
        
        return JSONResponse(content={
            "status": "success",
            "score": correct_answers,
            "total": total_questions,
            "percentage": round(score_percentage, 1),
            "daily_learning_capacity": daily_learning_capacity,
            "recommended_topics_per_day": recommended_topics_per_day,
            "analysis": analysis,
            "question_results": question_results
        })
    
    except Exception as e:
        logger.error(f"Error evaluating mock test: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

async def generate_analysis(correct_answers: int, total_questions: int, daily_learning_capacity: int) -> str:
    """
    Generate an analysis of the mock test results using OLLAMA
    """
    try:
        score_percentage = (correct_answers / total_questions) * 100 if total_questions > 0 else 0
        
        prompt = f"""
        Generate a personalized analysis for a student who has completed a mock test.
        
        Test Results:
        - Score: {correct_answers}/{total_questions} ({round(score_percentage, 1)}%)
        - Daily Learning Capacity Score: {daily_learning_capacity}/10
        
        Provide a 2-3 paragraph analysis that:
        1. Evaluates their performance in a constructive and encouraging way
        2. Explains what their Daily Learning Capacity Score means for their study approach
        3. Provides specific recommendations for how they should structure their study plan
        
        Keep the tone positive and motivational, even if the score is low.
        """
        
        result = run_ollama(prompt, model="llama3")
        
        # Clean up the result
        analysis = result.strip()
        
        return analysis
    
    except Exception as e:
        logger.error(f"Error generating analysis: {str(e)}")
        
        # Fallback analysis
        if correct_answers == total_questions:
            return "Excellent work! You've demonstrated a perfect understanding of the material. Your high Daily Learning Capacity Score suggests you can handle a challenging study load. Focus on advanced concepts and connections between topics."
        elif correct_answers >= total_questions * 0.7:
            return "Great job! You've shown a strong grasp of the material. Your Daily Learning Capacity Score indicates you can effectively learn multiple topics per day. Create a structured study plan that covers several related concepts each day."
        elif correct_answers >= total_questions * 0.5:
            return "Good effort! You've demonstrated a solid understanding of some key concepts. Your Daily Learning Capacity Score suggests you should focus on a moderate number of topics each day. Break complex ideas into smaller parts and build connections between related concepts."
        else:
            return "You've made a good start! Your Daily Learning Capacity Score suggests you should focus on mastering one or two topics per day. Take your time with each concept, use multiple learning methods, and practice regularly to reinforce your understanding."
