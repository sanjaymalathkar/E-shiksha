import os
import base64
import json
import asyncio
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
import logging
import google.generativeai as genai
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

# Import document chunking and embedding functionality
from app.core.embeddings import store_document_chunks, search_similar_chunks
from app.core.database import get_db
from app.core.ocr.document_processor import extract_text_from_file
from app.core.ollama.client import ollama_client

# Import cleanup utilities
from app.core.utils.cleanup import clean_temp_folder, schedule_file_deletion, clean_all_temp_files

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_ollama_model() -> str:
    """Pick preferred Ollama model, defaulting to llama3.2:3b."""
    preferred_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    models = ollama_client.list_models()
    available = [m.get("name", "") for m in models]

    if preferred_model in available:
        return preferred_model
    if available:
        return available[0]
    return preferred_model


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences so json.loads can parse model output."""
    t = (text or "").strip()
    if "```json" in t:
        t = t.split("```json", 1)[1].split("```", 1)[0].strip()
    elif t.startswith("```"):
        inner = t.strip("`")
        if inner.lower().startswith("json"):
            inner = inner[4:].lstrip()
        t = inner
    return t.strip()


def _coerce_topics(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str):
        parts = re.split(r"[,;\n]", val)
        return [p.strip() for p in parts if p.strip()]
    return [str(val).strip()] if str(val).strip() else []


def _coerce_time_allocation(val: Any) -> Dict[str, Union[float, str]]:
    if val is None:
        return {}
    if isinstance(val, dict):
        out: Dict[str, Union[float, str]] = {}
        for k, v in val.items():
            key = str(k).strip()
            if not key:
                continue
            if isinstance(v, (int, float)):
                out[key] = float(v)
            elif isinstance(v, str):
                m = re.search(r"([\d.]+)", v)
                out[key] = float(m.group(1)) if m else v
            else:
                out[key] = str(v)
        return out
    return {}


def _coerce_string_list(val: Any) -> List[str]:
    return _coerce_topics(val)


def _extract_day_entry(
    batch_content: Dict[str, Any],
    day_num: int,
    batch_start_day: int,
) -> Optional[Any]:
    """Find the plan object for an absolute day within a batch JSON object."""
    rel = day_num - batch_start_day + 1
    for key in (
        f"day_{day_num}",
        str(day_num),
        f"Day {day_num}",
        f"day_{rel}",
        str(rel),
        f"Day {rel}",
        f"Day_{day_num}",
        f"day_{rel}_plan",
    ):
        if key in batch_content:
            return batch_content[key]
    return None


def _normalize_plan_fields(
    raw: Any,
    day_num: int,
    plan_date: str,
    fallback_text: str = "",
) -> Dict[str, Any]:
    """Shape LLM output into the structure the planner UI expects."""
    if raw is None and fallback_text:
        raw = fallback_text
    if isinstance(raw, str):
        return {
            "day_number": day_num,
            "date": plan_date,
            "topics": [],
            "time_allocation": {},
            "key_concepts": [],
            "practice_items": [],
            "content": raw,
        }
    if not isinstance(raw, dict):
        return {
            "day_number": day_num,
            "date": plan_date,
            "topics": [],
            "time_allocation": {},
            "key_concepts": [],
            "practice_items": [],
            "content": fallback_text or str(raw),
        }

    topics = _coerce_topics(raw.get("topics"))
    key_concepts = _coerce_string_list(raw.get("key_concepts"))
    practice = raw.get("practice_items") or raw.get("practice") or raw.get("exercises")
    practice_items = _coerce_string_list(practice)
    time_allocation = _coerce_time_allocation(
        raw.get("time_allocation") or raw.get("time_allocations")
    )
    body = raw.get("content") or raw.get("summary") or raw.get("notes") or raw.get("description")
    content_str = body if isinstance(body, str) else ""

    plan: Dict[str, Any] = {
        "day_number": raw.get("day_number") or day_num,
        "date": raw.get("date") or plan_date,
        "topics": topics,
        "time_allocation": time_allocation,
        "key_concepts": key_concepts,
        "practice_items": practice_items,
    }
    if content_str:
        plan["content"] = content_str
    elif fallback_text and not topics and not key_concepts:
        plan["content"] = fallback_text
    return plan


def _extract_material_headings(text: str, max_headings: int = 80) -> List[str]:
    """
    Heuristic extraction of main headings from OCR / PDF-style plain text.
    Used when the study-plan model returns prose but empty structured fields.
    """
    if not text or not text.strip():
        return []
    seen: set = set()
    out: List[str] = []

    def push(line: str) -> None:
        line = line.strip()
        if len(line) < 8 or len(line) > 200:
            return
        if line in seen:
            return
        seen.add(line)
        out.append(line[:180])

    for raw in text.splitlines():
        line = raw.strip()
        if len(line) < 8 or len(line) > 200:
            continue
        if re.match(
            r"^(Chapter|Unit|Section|Part|Module|Lesson|Topic)\s+[\dIVXLC.\)\-]+",
            line,
            re.I,
        ):
            push(line)
            continue
        if re.match(r"^\d{1,2}[\.)]\s+[A-Za-z\u0900-\u0FFF]", line):
            push(re.sub(r"^\d{1,2}[\.)]\s+", "", line).strip() or line)
            continue
        if line.startswith("#"):
            push(line.lstrip("#").strip())
            continue
        letters = sum(1 for c in line if c.isalpha())
        if line.isupper() and letters >= 6:
            push(line)
            continue

    if len(out) < 6:
        for raw in text.splitlines():
            line = raw.strip()
            letters = sum(1 for c in line if c.isalpha())
            if 20 <= len(line) <= 120 and line and line[0].isupper():
                if line.endswith(":") and letters >= 8:
                    push(line[:-1])
                elif not line.endswith(".") and "http" not in line.lower():
                    words = line.split()
                    if 3 <= len(words) <= 14:
                        push(line)

    return out[:max_headings]


def _extract_key_concept_lines(text: str, max_items: int = 10) -> List[str]:
    """Bullet-like or numbered takeaway lines from study material."""
    if not text:
        return []
    found: List[str] = []
    seen: set = set()
    for raw in text.splitlines():
        line = raw.strip()
        if len(line) < 28 or len(line) > 280:
            continue
        if line.startswith(("-", "•", "*", "–", "—")):
            cleaned = line.lstrip("-•*–— ").strip()
        elif re.match(r"^\d{1,2}[\.)]\s+\S", line):
            cleaned = re.sub(r"^\d{1,2}[\.)]\s+", "", line).strip()
        else:
            continue
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            found.append(cleaned)
        if len(found) >= max_items + 6:
            break
    return found[:max_items]


def _enrich_plan_from_source_material(
    plan: Dict[str, Any],
    material: str,
    day_num: int,
    total_days: int,
) -> Dict[str, Any]:
    """
    Fill topics, time_allocation, and key_concepts using headings and bullets from the PDF text.
    """
    headings = _extract_material_headings(material)
    topics = _coerce_topics(plan.get("topics"))

    if not topics and headings:
        n = len(headings)
        total_days = max(1, min(total_days, 365))
        chunk = max(2, min(5, max(1, n // total_days)))
        start = ((day_num - 1) * chunk) % max(n, 1)
        topics = []
        for i in range(chunk):
            topics.append(headings[(start + i) % n])
        plan["topics"] = topics

    topics = _coerce_topics(plan.get("topics"))
    ta = _coerce_time_allocation(plan.get("time_allocation"))
    if topics and not ta:
        daily_budget = 6.0
        each = round(daily_budget / len(topics), 1)
        plan["time_allocation"] = {t: each for t in topics}
    elif topics and ta:
        plan["time_allocation"] = ta

    kc = _coerce_string_list(plan.get("key_concepts"))
    if not kc:
        bullets = _extract_key_concept_lines(material)
        if bullets:
            plan["key_concepts"] = bullets
        elif headings:
            take = headings[: min(8, len(headings))]
            plan["key_concepts"] = [f"Review and consolidate: {h}" for h in take]

    return plan


# Supported file formats and their MIME types
MIME_MAP = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
    '.pdf': 'application/pdf'  # PDF support
}

async def process_folder(
    folder_path: str,
    recursive: bool = False,
    exam_type: str = "",
    exam_date: str = ""
) -> Dict[str, Any]:
    """
    Process all files in a folder using Google Gemini model

    Args:
        folder_path: Path to the folder containing files to process
        recursive: Whether to process subfolders recursively
        exam_type: Type of exam the user is preparing for
        exam_date: Date when the user will take the exam

    Returns:
        Dictionary containing processing results
    """
    try:
        logger.info(f"Processing folder: {folder_path}")

        # Configure Google Gemini API when available; otherwise use Ollama fallback.
        api_key = os.getenv("GOOGLE_API_KEY")
        model = None
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-pro")

        # Get all files
        files = []
        if recursive:
            for root, _, filenames in os.walk(folder_path):
                for filename in filenames:
                    file_path = os.path.join(root, filename)
                    files.append(file_path)
        else:
            files = [os.path.join(folder_path, f) for f in os.listdir(folder_path)
                    if os.path.isfile(os.path.join(folder_path, f))]

        # Filter files by extension
        valid_files = []
        for file_path in files:
            ext = Path(file_path).suffix.lower()
            if ext in MIME_MAP:
                valid_files.append(file_path)

        logger.info(f"Found {len(valid_files)} valid files to process")

        # Process files in batches
        BATCH_SIZE = 5  # Process five files at a time for better throughput
        all_results = []

        for i in range(0, len(valid_files), BATCH_SIZE):
            batch_files = valid_files[i:i + BATCH_SIZE]

            logger.info(f"Processing batch {i//BATCH_SIZE + 1} of {(len(valid_files) + BATCH_SIZE - 1) // BATCH_SIZE} with {len(batch_files)} files...")

            # Prepare batch payloads
            batch_payloads = []
            batch_paths = []

            for file_path in batch_files:
                ext = Path(file_path).suffix.lower()
                mime_type = MIME_MAP[ext]

                try:
                    # Read file bytes
                    with open(file_path, "rb") as f:
                        file_data = f.read()

                    # Create payload
                    payload = {
                        'mime_type': mime_type,
                        'data': base64.b64encode(file_data).decode('utf-8')
                    }

                    batch_payloads.append(payload)
                    batch_paths.append(file_path)
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {str(e)}")

            if not batch_payloads:
                continue

            try:
                # Prepare prompt based on file type
                prompt = """
                Analyze the provided files. For each file:
                1. Extract all visible text content
                2. If tables are detected, convert them to structured format
                3. Identify key concepts, formulas, and important points
                4. Organize the content by topics and subtopics
                5. Format the output in a clean, readable structure
                """

                # Send to model
                contents = [prompt] + batch_payloads
                response = await asyncio.to_thread(
                    lambda: model.generate_content(contents)
                )

                # Process response
                extracted_text = response.text.strip()

                # Store in database with vector embeddings
                with get_db() as db:
                    for path in batch_paths:
                        # Create metadata for the document
                        metadata = {
                            "exam_type": exam_type,
                            "exam_date": exam_date,
                            "file_type": os.path.splitext(path)[1].lower(),
                            "processed_at": datetime.now().isoformat()
                        }

                        # Store document chunks with embeddings
                        chunk_ids = store_document_chunks(
                            file_path=path,
                            text=extracted_text,
                            metadata=metadata,
                            db=db
                        )

                        # Add to results
                        result = {
                            "file_path": path,
                            "file_name": os.path.basename(path),
                            "extracted_text": extracted_text,
                            "processed_at": datetime.now().isoformat(),
                            "chunk_ids": chunk_ids,
                            "chunks_count": len(chunk_ids)
                        }
                        all_results.append(result)

                logger.info(f"Successfully processed batch {i//BATCH_SIZE + 1}")
            except Exception as e:
                logger.error(f"Error processing batch {i//BATCH_SIZE + 1}: {str(e)}")
                # Fall back to local OCR/text extraction when Gemini is unavailable.
                for path in batch_paths:
                    fallback_text = extract_text_from_file(path)
                    if fallback_text and "Error:" not in fallback_text:
                        result = {
                            "file_path": path,
                            "file_name": os.path.basename(path),
                            "extracted_text": fallback_text,
                            "processed_at": datetime.now().isoformat()
                        }
                        all_results.append(result)
                        continue

                    result = {
                        "file_path": path,
                        "file_name": os.path.basename(path),
                        "extracted_text": f"Error: Failed to process file",
                        "processed_at": datetime.now().isoformat()
                    }
                    all_results.append(result)

        # Save results
        output_folder = os.getenv("OUTPUT_FOLDER", "data/output")
        os.makedirs(output_folder, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_folder, f"folder_results_{timestamp}.json")

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)

        # Generate test plans and study materials based on extracted content
        # Use asyncio.gather to run these tasks concurrently
        test_plans_task = asyncio.create_task(generate_test_plans(all_results, exam_type, exam_date))
        daily_content_task = asyncio.create_task(generate_daily_content(all_results, exam_type, exam_date))
        quotes_task = asyncio.create_task(get_motivational_quotes())

        # Wait for all tasks to complete
        test_plans, daily_content, motivational_quotes = await asyncio.gather(
            test_plans_task, daily_content_task, quotes_task
        )

        # Combine all results
        final_result = {
            "processed_files": len(all_results),
            "output_file": output_file,
            "exam_type": exam_type,
            "exam_date": exam_date,
            "test_plans": test_plans,
            "daily_content": daily_content,
            "motivational_quotes": motivational_quotes
        }

        # Schedule files for deletion after 10 minutes
        try:
            # Schedule all processed files for deletion after 10 minutes
            files_to_delete = []
            for file_path in valid_files:
                if os.path.exists(file_path):
                    files_to_delete.append(file_path)

            if files_to_delete:
                schedule_file_deletion(files_to_delete, delay_minutes=10)
                logger.info(f"Scheduled {len(files_to_delete)} files for deletion after 10 minutes")

            # Also clean up any older temporary files
            files_deleted, bytes_freed = clean_temp_folder(max_age_hours=1)  # Clean files older than 1 hour
            if files_deleted > 0:
                logger.info(f"Cleaned up {files_deleted} older temporary files, freed {bytes_freed/1024:.2f} KB")
        except Exception as cleanup_error:
            logger.warning(f"Error in file cleanup: {str(cleanup_error)}")

        return final_result
    except Exception as e:
        logger.error(f"Error in folder processing: {str(e)}")
        raise

async def generate_test_plans(
    results: List[Dict[str, Any]],
    exam_type: str,
    exam_date: str
) -> List[Dict[str, Any]]:
    """
    Generate test plans based on processed content

    Args:
        results: List of processing results
        exam_type: Type of exam
        exam_date: Date of exam

    Returns:
        List of test plans
    """
    def _fallback_with_ollama(content: str, days_until_exam: int) -> List[Dict[str, Any]]:
        model_name = _get_ollama_model()
        prompt = f"""
        Based on the following educational content, create 3 different test plans for a student preparing for the {exam_type} exam in {days_until_exam} days.
        Return valid JSON only.
        Content:
        {content[:10000]}
        """
        response = ollama_client.generate(
            prompt=prompt,
            model=model_name,
            temperature=0.3,
            max_tokens=2048
        )
        raw_text = response.get("response", "").strip()
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass

        return [
            {
                "title": f"Test Plan 1 for {exam_type}",
                "description": f"Generated with Ollama ({model_name})",
                "questions": raw_text or "Unable to generate test plan content."
            }
        ]

    try:
        logger.info(f"Generating test plans for {exam_type}")

        # Configure Google Gemini API when available; otherwise use Ollama fallback.
        api_key = os.getenv("GOOGLE_API_KEY")
        model = None
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-pro")

        # Get relevant content from vector database
        with get_db() as db:
            # Create a query to find relevant content for test planning
            query = f"Create test plans for {exam_type} exam with objective, subjective, and practical questions"

            # Search for similar chunks with metadata filter for this exam type
            metadata_filter = {"exam_type": exam_type} if exam_type else None
            relevant_chunks = search_similar_chunks(
                query=query,
                top_k=10,  # Get top 10 most relevant chunks
                metadata_filter=metadata_filter,
                db=db
            )

            # Extract content from chunks
            relevant_content = "\n\n".join([chunk["content"] for chunk in relevant_chunks])

            # If no relevant content found in vector DB, fall back to results
            if not relevant_content:
                logger.warning("No relevant content found in vector database, using raw results")
                # Check if we have any results with extracted text
                text_results = [result["extracted_text"] for result in results if "Error:" not in result.get("extracted_text", "")]
                if text_results:
                    relevant_content = "\n\n".join(text_results)
                    logger.info(f"Using {len(text_results)} raw text results as fallback")
                else:
                    # If we don't have any valid results, log an error
                    logger.error("No valid text content found in results")
                    return {
                        "status": "error",
                        "message": "No valid text content found in uploaded files",
                        "test_plans": []
                    }
            else:
                logger.info(f"Found {len(relevant_chunks)} relevant chunks in vector database")

        # Calculate days until exam
        days_until_exam = 90  # Default to 90 days
        try:
            exam_date_obj = datetime.strptime(exam_date, "%Y-%m-%d")
            today = datetime.now()
            days_until_exam = (exam_date_obj - today).days
            if days_until_exam < 1:
                days_until_exam = 90  # Default if date is in the past
        except:
            logger.warning(f"Could not parse exam date: {exam_date}, using default 90 days")

        # Generate test plans
        prompt = f"""
        Based on the following educational content, create 3 different test plans for a student preparing for the {exam_type} exam in {days_until_exam} days.

        For each test plan:
        1. Create a title and description
        2. Include 10 questions with varying difficulty levels (easy, medium, hard)
        3. For each question, provide the correct answer and explanation
        4. Group questions by topic
        5. Include a time estimate for each test
        6. Format the output as a structured JSON

        Content:
        {relevant_content[:10000]}  # Limit content length to avoid token limits
        """

        try:
            response = await asyncio.to_thread(
                lambda: model.generate_content(prompt)
            )

            # Parse response as JSON
            try:
                test_plans = json.loads(response.text)
            except:
                # If not valid JSON, return as text
                test_plans = [
                    {
                        "title": f"Test Plan 1 for {exam_type}",
                        "description": "Generated test plan",
                        "questions": response.text
                    }
                ]
        except Exception as gemini_error:
            logger.warning(f"Gemini test plan generation failed, falling back to Ollama: {str(gemini_error)}")
            test_plans = _fallback_with_ollama(relevant_content, days_until_exam)

        # Save test plans
        output_folder = os.getenv("OUTPUT_FOLDER", "data/output")
        test_plans_file = os.path.join(output_folder, f"test_plans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        with open(test_plans_file, 'w', encoding='utf-8') as f:
            json.dump(test_plans, f, ensure_ascii=False, indent=2)

        return test_plans
    except Exception as e:
        logger.error(f"Error generating test plans: {str(e)}")
        return [{"error": str(e)}]

async def generate_daily_content(
    results: List[Dict[str, Any]],
    exam_type: str,
    exam_date: str
) -> Dict[str, Any]:
    """
    Generate daily study content based on processed files

    Args:
        results: List of processing results
        exam_type: Type of exam
        exam_date: Date of exam

    Returns:
        Dictionary with daily content plan
    """
    try:
        logger.info(f"Generating daily content for {exam_type}")

        api_key = os.getenv("GOOGLE_API_KEY")
        model = None
        if api_key:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-1.5-pro")
            except Exception as gemini_init_err:
                logger.warning(f"Gemini unavailable for daily content ({gemini_init_err}); using Ollama.")
        else:
            logger.warning("GOOGLE_API_KEY not set; generating daily study plans with local Ollama.")

        # Get relevant content from vector database
        with get_db() as db:
            # Create a query to find relevant content for daily study planning
            query = f"Create daily study plan for {exam_type} exam with topics, time allocation, and practice exercises"

            # Search for similar chunks with metadata filter for this exam type
            metadata_filter = {"exam_type": exam_type} if exam_type else None
            relevant_chunks = search_similar_chunks(
                query=query,
                top_k=15,  # Get top 15 most relevant chunks for more comprehensive content
                metadata_filter=metadata_filter,
                db=db
            )

            # Extract content from chunks
            relevant_content = "\n\n".join([chunk["content"] for chunk in relevant_chunks])

            # If no relevant content found in vector DB, fall back to results
            if not relevant_content:
                logger.warning("No relevant content found in vector database, using raw results")
                # Check if we have any results with extracted text
                text_results = [result["extracted_text"] for result in results if "Error:" not in result.get("extracted_text", "")]
                if text_results:
                    relevant_content = "\n\n".join(text_results)
                    logger.info(f"Using {len(text_results)} raw text results as fallback for daily content")
                else:
                    # If we don't have any valid results, log an error
                    logger.error("No valid text content found in results for daily content")
                    return {
                        "status": "error",
                        "message": "No valid text content found in uploaded files",
                        "daily_plans": {}
                    }
            else:
                logger.info(f"Found {len(relevant_chunks)} relevant chunks in vector database for daily content")

        # Calculate days until exam
        days_until_exam = 90  # Default to 90 days
        try:
            exam_date_obj = datetime.strptime(exam_date, "%Y-%m-%d")
            today = datetime.now()
            days_until_exam = (exam_date_obj - today).days
            if days_until_exam < 1:
                days_until_exam = 90  # Default if date is in the past
        except:
            logger.warning(f"Could not parse exam date: {exam_date}, using default 90 days")

        # Calculate how many batches of 8 days we need to generate
        num_batches = (days_until_exam + 7) // 8  # Ceiling division
        if num_batches < 1:
            num_batches = 1

        # Generate study plans in batches of 8 days
        all_daily_content = {}
        current_date = datetime.now()

        for batch in range(num_batches):
            batch_start_day = batch * 8 + 1
            batch_end_day = min((batch + 1) * 8, days_until_exam)

            # Skip if we've already covered all days
            if batch_start_day > days_until_exam:
                break

            logger.info(f"Generating study plan for days {batch_start_day} to {batch_end_day}")

            # Generate prompt for this batch
            prompt = f"""
            Based on the following educational content, create a daily study plan for a student preparing for the {exam_type} exam.

            Generate a detailed study plan for days {batch_start_day} to {batch_end_day} of the preparation.

            IMPORTANT:
            - Derive topic titles from real chapter/section headings and titles that appear in the source text below
              (e.g. lines starting with Chapter, Section, numbered sections like "1. Introduction", or ALL CAPS headings).
            - For each day, topics must be non-empty arrays of specific titles (not generic placeholders).
            - time_allocation must map EACH topic string to study hours (numbers); daily total should be roughly 5–8 hours.
            - key_concepts must list concrete ideas from the material for that day (short phrases).

            DO NOT include mock tests.

            Format the output as a structured JSON object. Use one key per calendar day: "day_{N}" where N is the
            absolute day number (1 to {days_until_exam}), not a batch-relative index. Each value must be an object with:
            - topics: array of strings (from document headings)
            - time_allocation: object mapping each topic name exactly to hours (numeric)
            - practice: array of short exercise descriptions
            - key_concepts: array of strings (specific ideas to master)

            Content:
            {relevant_content[:12000]}  # Limit content length to avoid token limits
            """

            response_text = ""
            if model is not None:
                try:
                    response = await asyncio.to_thread(
                        lambda p=prompt: model.generate_content(p)
                    )
                    response_text = (response.text or "").strip()
                except Exception as e:
                    logger.warning(
                        f"Gemini daily content generation failed for batch {batch}, will try Ollama: {str(e)}"
                    )

            if not response_text:
                ollama_model = _get_ollama_model()
                ollama_response = await asyncio.to_thread(
                    lambda: ollama_client.generate(
                        prompt=prompt,
                        model=ollama_model,
                        temperature=0.3,
                        max_tokens=4096,
                    )
                )
                response_text = (ollama_response.get("response") or "").strip()

            batch_content: Optional[Dict[str, Any]] = None
            try:
                batch_content = json.loads(_strip_json_fences(response_text))
            except json.JSONDecodeError:
                logger.info(f"Batch {batch} response was not valid JSON; storing as text per day.")

            if isinstance(batch_content, dict):
                for day_num in range(batch_start_day, batch_end_day + 1):
                    plan_date = (current_date + timedelta(days=day_num - 1)).strftime("%Y-%m-%d")
                    raw = _extract_day_entry(batch_content, day_num, batch_start_day)
                    if raw is None:
                        raw = response_text
                    norm = _normalize_plan_fields(
                        raw, day_num, plan_date, fallback_text=response_text
                    )
                    all_daily_content[f"day_{day_num}"] = _enrich_plan_from_source_material(
                        norm, relevant_content, day_num, days_until_exam
                    )
            else:
                for day_num in range(batch_start_day, batch_end_day + 1):
                    plan_date = (current_date + timedelta(days=day_num - 1)).strftime("%Y-%m-%d")
                    norm = _normalize_plan_fields(
                        response_text, day_num, plan_date, fallback_text=response_text
                    )
                    all_daily_content[f"day_{day_num}"] = _enrich_plan_from_source_material(
                        norm, relevant_content, day_num, days_until_exam
                    )

        # Add metadata
        final_content = {
            "exam_type": exam_type,
            "exam_date": exam_date,
            "days_until_exam": days_until_exam,
            "generated_at": datetime.now().isoformat(),
            "daily_plans": all_daily_content
        }

        # Save daily content
        output_folder = os.getenv("OUTPUT_FOLDER", "data/output")
        daily_content_file = os.path.join(output_folder, f"daily_content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

        with open(daily_content_file, 'w', encoding='utf-8') as f:
            json.dump(final_content, f, ensure_ascii=False, indent=2)

        return final_content
    except Exception as e:
        logger.error(f"Error generating daily content: {str(e)}")
        return {"error": str(e)}

async def get_motivational_quotes() -> List[str]:
    """
    Get motivational quotes for students

    Returns:
        List of motivational quotes
    """
    try:
        logger.info("Getting motivational quotes")

        # Configure Google Gemini API when available; otherwise use Ollama fallback.
        api_key = os.getenv("GOOGLE_API_KEY")
        model = None
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-1.5-flash")

        # Generate quotes
        prompt = """
        Generate 10 motivational quotes for students preparing for exams.
        Each quote should be inspiring, concise, and focused on academic success.
        Format the output as a JSON array of strings.
        """

        try:
            response = await asyncio.to_thread(
                lambda: model.generate_content(prompt)
            )

            # Parse response as JSON
            try:
                quotes = json.loads(response.text)
            except:
                # If not valid JSON, extract quotes from text
                text = response.text
                lines = text.strip().split('\n')
                quotes = [line.strip() for line in lines if line.strip()]
        except Exception as gemini_error:
            logger.warning(f"Gemini quotes generation failed, falling back to Ollama: {str(gemini_error)}")
            model_name = _get_ollama_model()
            ollama_response = ollama_client.generate(
                prompt=prompt,
                model=model_name,
                temperature=0.7,
                max_tokens=512
            )
            text = ollama_response.get("response", "")
            lines = text.strip().split('\n')
            quotes = [line.strip("-* ").strip() for line in lines if line.strip()]

        return quotes
    except Exception as e:
        logger.error(f"Error getting motivational quotes: {str(e)}")
        return [
            "The harder you work for something, the greater you'll feel when you achieve it.",
            "Success is the sum of small efforts, repeated day in and day out.",
            "Don't wish it were easier; wish you were better.",
            "The expert in anything was once a beginner.",
            "The only way to do great work is to love what you do."
        ]
