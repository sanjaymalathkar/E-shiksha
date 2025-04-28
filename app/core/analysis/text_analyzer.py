import re
import json
import os
from typing import Dict, Any, List, Optional
import logging
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Download NLTK resources
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
except Exception as e:
    logger.warning(f"Failed to download NLTK resources: {str(e)}")

async def analyze_text(
    text: str,
    language: str = "en",
    file_type: str = "pdf"
) -> Dict[str, Any]:
    """
    Analyze text content to extract educational information

    Args:
        text: The text to analyze
        language: The language of the text
        file_type: The type of file the text was extracted from

    Returns:
        Dictionary containing the analysis results
    """
    try:
        # Extract questions and marks
        questions = await extract_questions(text)

        # Extract keywords
        keywords = await extract_keywords(text)

        # Identify topics/chapters
        topics = await identify_topics(text)

        # Categorize questions
        categorized_questions = await categorize_questions(questions)

        # Calculate marks distribution
        marks_distribution = await calculate_marks_distribution(questions)

        # Create analysis result
        result = {
            "questions": questions,
            "keywords": keywords,
            "topics": topics,
            "categorized_questions": categorized_questions,
            "marks_distribution": marks_distribution,
            "language": language,
            "file_type": file_type
        }

        # Save analysis result
        output_folder = os.getenv("OUTPUT_FOLDER", "data/output")
        os.makedirs(output_folder, exist_ok=True)

        output_file = os.path.join(
            output_folder,
            f"analysis_{os.urandom(4).hex()}.json"
        )

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return result
    except Exception as e:
        logger.error(f"Error analyzing text: {str(e)}")
        raise

async def extract_questions(text: str) -> List[Dict[str, Any]]:
    """
    Extract questions and their marks from text

    Args:
        text: The text to extract questions from

    Returns:
        List of dictionaries containing questions and their marks
    """
    questions = []

    # Split text into sentences
    sentences = sent_tokenize(text)

    # Regular expression to match question patterns
    question_pattern = r'(\d+)\.\s+(.*?)(?:\[(\d+)\s*marks?\]|\((\d+)\s*marks?\))?'

    for sentence in sentences:
        # Check if sentence contains a question
        match = re.search(question_pattern, sentence, re.IGNORECASE)
        if match:
            question_num = match.group(1)
            question_text = match.group(2).strip()
            marks = match.group(3) or match.group(4) or "1"  # Default to 1 mark if not specified

            questions.append({
                "number": question_num,
                "text": question_text,
                "marks": int(marks)
            })

    return questions

async def extract_keywords(text: str) -> List[str]:
    """
    Extract keywords from text

    Args:
        text: The text to extract keywords from

    Returns:
        List of keywords
    """
    # Tokenize text
    words = word_tokenize(text.lower())

    # Remove stopwords
    stop_words = set(stopwords.words('english'))
    filtered_words = [word for word in words if word.isalnum() and word not in stop_words]

    # Count word frequencies
    word_freq = {}
    for word in filtered_words:
        if word in word_freq:
            word_freq[word] += 1
        else:
            word_freq[word] = 1

    # Sort by frequency
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    # Return top 20 keywords
    return [word for word, freq in sorted_words[:20]]

async def identify_topics(text: str) -> List[str]:
    """
    Identify topics or chapters from text using NLP techniques

    Args:
        text: The text to identify topics from

    Returns:
        List of topics
    """
    try:
        # Try to use Ollama for more sophisticated topic extraction
        from app.core.ollama_local import run_ollama_json

        # Limit text length to avoid token limits
        max_text_length = 4000
        truncated_text = text[:max_text_length] if len(text) > max_text_length else text

        prompt = f"""
        Extract the main educational topics from the following text.
        Identify subject areas, concepts, and themes that would be relevant for creating study materials.
        Return the result as a JSON array of strings, with each string being a distinct topic.
        Focus on extracting 5-10 clear, specific topics.

        Text:
        {truncated_text}
        """

        result = run_ollama_json(prompt, model="llama3")

        if isinstance(result, list) and len(result) > 0:
            # Clean up topics
            topics = [topic.strip() for topic in result if isinstance(topic, str) and topic.strip()]
            # Remove duplicates and limit to top 15
            unique_topics = list(set(topics))
            return unique_topics[:15]

    except Exception as e:
        logger.warning(f"Error using Ollama for topic extraction: {e}. Falling back to rule-based extraction.")

    # Fallback: Define common educational topics
    common_topics = {
        "math": ["algebra", "geometry", "calculus", "trigonometry", "statistics", "probability"],
        "science": ["physics", "chemistry", "biology", "ecology", "astronomy", "geology"],
        "english": ["grammar", "literature", "poetry", "prose", "writing", "comprehension"],
        "history": ["ancient", "medieval", "modern", "world war", "civilization", "revolution"],
        "geography": ["map", "climate", "population", "ecosystem", "continent", "country"]
    }

    # Convert text to lowercase for case-insensitive matching
    text_lower = text.lower()

    # Identify topics
    identified_topics = []

    # Method 1: Use predefined topics
    for subject, topics in common_topics.items():
        if subject in text_lower:
            identified_topics.append(subject)

        for topic in topics:
            if topic in text_lower:
                identified_topics.append(f"{subject}: {topic}")

    # Method 2: Look for capitalized phrases that might be topics
    lines = text.split('\n')
    for line in lines:
        # Check if line is a potential topic (short, capitalized)
        if len(line.strip()) > 0 and len(line.strip()) < 50 and line.strip()[0].isupper():
            # Check if more than 50% of words start with uppercase
            words = line.strip().split()
            if len(words) > 0 and len(words) < 8:  # Avoid long sentences
                uppercase_ratio = sum(1 for word in words if word and word[0].isupper()) / len(words)
                if uppercase_ratio > 0.5:
                    identified_topics.append(line.strip())

    # Method 3: Look for phrases that appear after "Chapter", "Section", "Topic", etc.
    chapter_pattern = re.compile(r'(Chapter|Section|Topic|Unit|Module|Part)\s+\d*\s*[:\-]?\s*([A-Z][^\.!?]*)')
    for match in chapter_pattern.finditer(text):
        if match.group(2):
            identified_topics.append(match.group(2).strip())

    # Remove duplicates and limit to top 15
    return list(set(identified_topics))[:15]

async def categorize_questions(questions: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Categorize questions into objective, subjective, and practical

    Args:
        questions: List of questions to categorize

    Returns:
        Dictionary with categorized questions
    """
    objective = []
    subjective = []
    practical = []

    for question in questions:
        text = question["text"].lower()

        # Objective questions are typically short and have specific answers
        if any(keyword in text for keyword in ["what is", "name", "identify", "choose", "select", "true or false", "multiple choice"]):
            objective.append(question)

        # Practical questions involve application or problem-solving
        elif any(keyword in text for keyword in ["calculate", "compute", "solve", "find", "determine", "design", "experiment", "apply"]):
            practical.append(question)

        # Subjective questions require explanation or discussion
        elif any(keyword in text for keyword in ["explain", "describe", "discuss", "analyze", "compare", "contrast", "evaluate", "prove"]):
            subjective.append(question)

        # Default to subjective if can't determine
        else:
            subjective.append(question)

    return {
        "objective": objective,
        "subjective": subjective,
        "practical": practical
    }

async def calculate_marks_distribution(questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate marks distribution from questions

    Args:
        questions: List of questions with marks

    Returns:
        Dictionary with marks distribution
    """
    total_marks = sum(question["marks"] for question in questions)

    # Calculate marks by question type
    marks_by_type = {}

    # Categorize questions
    categorized = await categorize_questions(questions)

    for category, category_questions in categorized.items():
        category_marks = sum(question["marks"] for question in category_questions)
        marks_by_type[category] = {
            "marks": category_marks,
            "percentage": round((category_marks / total_marks) * 100, 2) if total_marks > 0 else 0
        }

    return {
        "total_marks": total_marks,
        "by_type": marks_by_type
    }
