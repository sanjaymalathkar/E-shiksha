import os
import logging
import tempfile
import shutil
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse

from app.core.ollama.processor import (
    process_files_with_ollama,
    generate_test_plan_with_ollama,
    generate_daily_content_with_ollama
)
from app.core.utils import schedule_file_deletion, generate_pdf_from_analysis

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    tags=["ollama"],
    responses={404: {"description": "Not found"}},
)

def filter_important_content(text):
    """Filter text to keep only important content for studying"""
    if not text:
        return ""

    # Split text into lines
    lines = text.split('\n')
    important_lines = []

    # Keywords that indicate important content
    important_keywords = [
        "definition", "formula", "equation", "theorem", "principle",
        "important", "essential", "critical", "key", "fundamental",
        "remember", "note", "example", "property", "characteristic",
        "concept", "rule", "law", "theory", "method", "technique",
        "approach", "strategy", "framework", "structure", "relationship"
    ]

    # Process each line
    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Keep lines that are likely to be important
        if any(keyword in line.lower() for keyword in important_keywords):
            important_lines.append(line)
        # Keep lines that are likely to be headings
        elif line.isupper() or (len(line) < 100 and line[0].isupper() and not line.endswith('.')):
            important_lines.append(line)
        # Keep lines with bullet points or numbering
        elif line.startswith('-') or line.startswith('•') or (len(line) > 2 and line[0].isdigit() and line[1] in ['.', ')']):
            important_lines.append(line)
        # Keep lines with formulas (containing = or mathematical symbols)
        elif '=' in line or any(symbol in line for symbol in ['+', '-', '*', '/', '^', '√', '∫', '∑', '∏', '∆', '∇']):
            important_lines.append(line)

    # Join the important lines back together
    return '\n'.join(important_lines)

@router.post("/process")
async def process_files(
    files: List[UploadFile] = File(...),
    task_description: str = Form(...),
    exam_type: Optional[str] = Form(None),
    model: str = Form("deepseek-r1:1.5b")
):
    """
    Process multiple files using Ollama
    """
    try:
        # Create temporary directory for files
        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths = []

            # Save uploaded files to temporary directory
            for file in files:
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as f:
                    f.write(await file.read())
                file_paths.append(file_path)

            # Process files
            result = process_files_with_ollama(
                file_paths=file_paths,
                task_description=task_description,
                model=model,
                exam_type=exam_type
            )

            # Schedule files for deletion after 10 minutes
            # We need to copy the files to a persistent location first since the temp directory will be deleted
            persistent_files = []
            data_temp_dir = os.path.join("data", "temp")
            os.makedirs(data_temp_dir, exist_ok=True)

            for file_path in file_paths:
                try:
                    # Copy file to data/temp directory
                    file_name = os.path.basename(file_path)
                    dest_path = os.path.join(data_temp_dir, file_name)
                    shutil.copy2(file_path, dest_path)
                    persistent_files.append(dest_path)
                    logger.info(f"Copied file to persistent location: {dest_path}")
                except Exception as copy_error:
                    logger.error(f"Error copying file to persistent location: {str(copy_error)}")

            # Schedule the persistent files for deletion after 10 minutes
            if persistent_files:
                schedule_file_deletion(persistent_files, delay_minutes=10)
                logger.info(f"Scheduled {len(persistent_files)} files for deletion after 10 minutes")

            return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error processing files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing files: {str(e)}")

@router.post("/test-plan")
async def generate_test_plan(
    files: List[UploadFile] = File(...),
    exam_type: Optional[str] = Form(None),
    model: str = Form("deepseek-r1:1.5b")
):
    """
    Generate a test plan from multiple files using Ollama
    """
    try:
        # Create temporary directory for files
        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths = []

            # Save uploaded files to temporary directory
            for file in files:
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as f:
                    f.write(await file.read())
                file_paths.append(file_path)

            # Generate test plan
            result = generate_test_plan_with_ollama(
                file_paths=file_paths,
                exam_type=exam_type,
                model=model
            )

            # Schedule files for deletion after 10 minutes
            # We need to copy the files to a persistent location first since the temp directory will be deleted
            persistent_files = []
            data_temp_dir = os.path.join("data", "temp")
            os.makedirs(data_temp_dir, exist_ok=True)

            for file_path in file_paths:
                try:
                    # Copy file to data/temp directory
                    file_name = os.path.basename(file_path)
                    dest_path = os.path.join(data_temp_dir, file_name)
                    shutil.copy2(file_path, dest_path)
                    persistent_files.append(dest_path)
                    logger.info(f"Copied file to persistent location: {dest_path}")
                except Exception as copy_error:
                    logger.error(f"Error copying file to persistent location: {str(copy_error)}")

            # Schedule the persistent files for deletion after 10 minutes
            if persistent_files:
                schedule_file_deletion(persistent_files, delay_minutes=10)
                logger.info(f"Scheduled {len(persistent_files)} files for deletion after 10 minutes")

            return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error generating test plan: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating test plan: {str(e)}")

@router.post("/daily-content")
async def generate_daily_content(
    files: List[UploadFile] = File(...),
    exam_type: Optional[str] = Form(None),
    model: str = Form("deepseek-r1:1.5b")
):
    """
    Generate daily study content from multiple files using Ollama
    """
    try:
        # Create temporary directory for files
        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths = []

            # Save uploaded files to temporary directory
            for file in files:
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as f:
                    f.write(await file.read())
                file_paths.append(file_path)

            # Generate daily content
            result = generate_daily_content_with_ollama(
                file_paths=file_paths,
                exam_type=exam_type,
                model=model
            )

            # Schedule files for deletion after 10 minutes
            # We need to copy the files to a persistent location first since the temp directory will be deleted
            persistent_files = []
            data_temp_dir = os.path.join("data", "temp")
            os.makedirs(data_temp_dir, exist_ok=True)

            for file_path in file_paths:
                try:
                    # Copy file to data/temp directory
                    file_name = os.path.basename(file_path)
                    dest_path = os.path.join(data_temp_dir, file_name)
                    shutil.copy2(file_path, dest_path)
                    persistent_files.append(dest_path)
                    logger.info(f"Copied file to persistent location: {dest_path}")
                except Exception as copy_error:
                    logger.error(f"Error copying file to persistent location: {str(copy_error)}")

            # Schedule the persistent files for deletion after 10 minutes
            if persistent_files:
                schedule_file_deletion(persistent_files, delay_minutes=10)
                logger.info(f"Scheduled {len(persistent_files)} files for deletion after 10 minutes")

            return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error generating daily content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating daily content: {str(e)}")

@router.get("/models")
async def list_models():
    """
    List available Ollama models
    """
    try:
        from app.core.ollama.client import ollama_client
        models = ollama_client.list_models()
        return JSONResponse(content={"models": models})

    except Exception as e:
        logger.error(f"Error listing models: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing models: {str(e)}")

@router.get("/status")
async def check_status():
    """
    Check Ollama server status
    """
    try:
        from app.core.ollama.client import ollama_client
        status = ollama_client.test_connection()
        return JSONResponse(content={"status": "connected" if status else "disconnected"})

    except Exception as e:
        logger.error(f"Error checking Ollama status: {str(e)}")
        return JSONResponse(content={"status": "disconnected", "error": str(e)})

@router.post("/generate-pdf")
async def generate_pdf(
    files: List[UploadFile] = File(...),
    exam_type: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    model: str = Form("deepseek-r1:1.5b")
):
    """
    Process files with Ollama using Deepseek model and generate a downloadable PDF
    with thorough content analysis, just like the daily planner
    """
    try:
        # Create temporary directory for files
        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths = []

            # Save uploaded files to temporary directory
            for file in files:
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as f:
                    f.write(await file.read())
                file_paths.append(file_path)

            logger.info(f"Saved {len(file_paths)} files to temporary directory for PDF generation")

            # Create a focused key points extraction prompt
            task_description = """
            Extract and summarize ONLY the most important key points from the educational content in these files.

            Focus exclusively on:
            1. Essential concepts and definitions that must be memorized
            2. Critical formulas and principles that are frequently tested
            3. Key relationships between concepts that are fundamental to understanding
            4. Important examples that illustrate core principles

            DO NOT include:
            - Generic test plan structures or templates
            - Objective or subjective questions
            - Practical exercises or time allocations
            - Grading criteria or assessment frameworks
            - Lengthy explanations or background information
            - Introductory or contextual material
            - Repetitive or redundant information

            Format your response as concise bullet points organized by topic.
            Each point should be brief, clear, and directly relevant to exam preparation.
            Use bold formatting for the most critical points that must be memorized.

            The goal is to create a condensed, high-value study guide containing only the essential
            information a student needs to know for exam preparation.
            """

            # Process files with Ollama using Deepseek model
            result = process_files_with_ollama(
                file_paths=file_paths,
                task_description=task_description,
                model=model,
                exam_type=exam_type
            )

            logger.info(f"Ollama processing completed with {len(file_paths)} files processed")

            # Extract the raw text from the uploaded files
            from app.core.ollama.processor import extract_text_from_files

            # Extract text from all files
            extracted_texts = []
            file_names = []

            for file_path in file_paths:
                try:
                    # Extract text from the file
                    extracted_text = extract_text_from_files([file_path])
                    if extracted_text:
                        # Filter the extracted text to keep only important content
                        filtered_text = filter_important_content(extracted_text)
                        extracted_texts.append(filtered_text)
                    file_names.append(os.path.basename(file_path))
                except Exception as e:
                    logger.error(f"Error extracting text from {file_path}: {str(e)}")

            # Combine the Ollama analysis with selected extracted text
            content_parts = []

            # Add title and metadata
            content_parts.append(f"# Key Study Points for {exam_type or 'General Education'}")
            content_parts.append(f"Generated on: {datetime.now().strftime('%B %d, %Y')}")

            # Add the Ollama analysis (key points)
            if result.get("result"):
                content_parts.append("\n" + result["result"])
            else:
                # If no result from Ollama, create a focused key points summary
                content_parts.append("\n## Essential Concepts")
                content_parts.append("- **Core principles** that form the foundation of the subject")
                content_parts.append("- **Key terminology** necessary for understanding the material")
                content_parts.append("- **Fundamental relationships** between important concepts")

                content_parts.append("\n## Critical Formulas and Methods")
                content_parts.append("- **Essential equations** that appear frequently in exams")
                content_parts.append("- **Step-by-step procedures** for solving common problems")
                content_parts.append("- **Application techniques** for practical scenarios")

                content_parts.append("\n## Important Examples")
                content_parts.append("- **Illustrative cases** that demonstrate key principles")
                content_parts.append("- **Common problem types** with solution approaches")
                content_parts.append("- **Edge cases** that test deeper understanding")

            # Add selected important excerpts from the text
            if extracted_texts:
                content_parts.append("\n## Important Excerpts")

                # Add only the most important excerpts from each file
                for i, (text, name) in enumerate(zip(extracted_texts, file_names)):
                    # Extract only the most important parts (first 1000 chars max)
                    important_excerpt = text[:1000] + "..." if len(text) > 1000 else text
                    content_parts.append(f"\n### From {name}")
                    content_parts.append(important_excerpt)

            # Combine all parts into a single string
            result["result"] = "\n".join(content_parts)

            # Schedule files for deletion after 10 minutes
            # We need to copy the files to a persistent location first since the temp directory will be deleted
            persistent_files = []
            data_temp_dir = os.path.join("data", "temp")
            os.makedirs(data_temp_dir, exist_ok=True)

            for file_path in file_paths:
                try:
                    # Copy file to data/temp directory
                    file_name = os.path.basename(file_path)
                    dest_path = os.path.join(data_temp_dir, file_name)
                    shutil.copy2(file_path, dest_path)
                    persistent_files.append(dest_path)
                    logger.info(f"Copied file to persistent location: {dest_path}")
                except Exception as copy_error:
                    logger.error(f"Error copying file to persistent location: {str(copy_error)}")

            # Schedule the persistent files for deletion after 10 minutes
            if persistent_files:
                schedule_file_deletion(persistent_files, delay_minutes=10)
                logger.info(f"Scheduled {len(persistent_files)} files for deletion after 10 minutes")

            # Generate PDF from analysis result
            pdf_title = title if title else f"Analysis for {exam_type}" if exam_type else "Content Analysis"

            # Log the analysis result for debugging
            logger.info(f"Analysis result status: {result.get('status')}")
            logger.info(f"Analysis result contains content: {'Yes' if result.get('result') else 'No'}")

            # If there's no content in the result, log an error
            if not result.get("result"):
                logger.error("No content in analysis result. This should not happen with proper analysis.")

            pdf_path = generate_pdf_from_analysis(
                analysis_result=result,
                exam_type=exam_type,
                title=pdf_title
            )

            # Schedule PDF for deletion after 10 minutes
            schedule_file_deletion([pdf_path], delay_minutes=10)
            logger.info(f"Scheduled PDF for deletion after 10 minutes: {pdf_path}")

            # Return the PDF file
            return FileResponse(
                path=pdf_path,
                filename=os.path.basename(pdf_path),
                media_type="application/pdf"
            )

    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

@router.post("/daily-content-pdf")
async def generate_daily_content_pdf(
    files: List[UploadFile] = File(...),
    exam_type: Optional[str] = Form(None),
    model: str = Form("deepseek-r1:1.5b")
):
    """
    Generate daily study content from multiple files and return as PDF
    """
    try:
        # Create temporary directory for files
        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths = []

            # Save uploaded files to temporary directory
            for file in files:
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as f:
                    f.write(await file.read())
                file_paths.append(file_path)

            # Generate daily content
            result = generate_daily_content_with_ollama(
                file_paths=file_paths,
                exam_type=exam_type,
                model=model
            )

            # Schedule files for deletion after 10 minutes
            # We need to copy the files to a persistent location first since the temp directory will be deleted
            persistent_files = []
            data_temp_dir = os.path.join("data", "temp")
            os.makedirs(data_temp_dir, exist_ok=True)

            for file_path in file_paths:
                try:
                    # Copy file to data/temp directory
                    file_name = os.path.basename(file_path)
                    dest_path = os.path.join(data_temp_dir, file_name)
                    shutil.copy2(file_path, dest_path)
                    persistent_files.append(dest_path)
                    logger.info(f"Copied file to persistent location: {dest_path}")
                except Exception as copy_error:
                    logger.error(f"Error copying file to persistent location: {str(copy_error)}")

            # Schedule the persistent files for deletion after 10 minutes
            if persistent_files:
                schedule_file_deletion(persistent_files, delay_minutes=10)
                logger.info(f"Scheduled {len(persistent_files)} files for deletion after 10 minutes")

            # Generate PDF from analysis result
            pdf_title = f"Daily Study Plan for {exam_type}" if exam_type else "Daily Study Plan"

            # Log the analysis result for debugging
            logger.info(f"Daily study plan result status: {result.get('status')}")
            logger.info(f"Daily study plan contains content: {'Yes' if result.get('result') else 'No'}")

            # If there's no content in the result, log an error
            if not result.get("result"):
                logger.error("No content in daily study plan result. This should not happen with proper analysis.")

            pdf_path = generate_pdf_from_analysis(
                analysis_result=result,
                exam_type=exam_type,
                title=pdf_title
            )

            # Schedule PDF for deletion after 10 minutes
            schedule_file_deletion([pdf_path], delay_minutes=10)
            logger.info(f"Scheduled PDF for deletion after 10 minutes: {pdf_path}")

            # Return the PDF file
            return FileResponse(
                path=pdf_path,
                filename=os.path.basename(pdf_path),
                media_type="application/pdf"
            )

    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

@router.post("/test-plan-pdf")
async def generate_test_plan_pdf(
    files: List[UploadFile] = File(...),
    exam_type: Optional[str] = Form(None),
    model: str = Form("deepseek-r1:1.5b")
):
    """
    Generate a test plan from multiple files and return as PDF
    """
    try:
        # Create temporary directory for files
        with tempfile.TemporaryDirectory() as temp_dir:
            file_paths = []

            # Save uploaded files to temporary directory
            for file in files:
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as f:
                    f.write(await file.read())
                file_paths.append(file_path)

            # Generate test plan
            result = generate_test_plan_with_ollama(
                file_paths=file_paths,
                exam_type=exam_type,
                model=model
            )

            # Schedule files for deletion after 10 minutes
            # We need to copy the files to a persistent location first since the temp directory will be deleted
            persistent_files = []
            data_temp_dir = os.path.join("data", "temp")
            os.makedirs(data_temp_dir, exist_ok=True)

            for file_path in file_paths:
                try:
                    # Copy file to data/temp directory
                    file_name = os.path.basename(file_path)
                    dest_path = os.path.join(data_temp_dir, file_name)
                    shutil.copy2(file_path, dest_path)
                    persistent_files.append(dest_path)
                    logger.info(f"Copied file to persistent location: {dest_path}")
                except Exception as copy_error:
                    logger.error(f"Error copying file to persistent location: {str(copy_error)}")

            # Schedule the persistent files for deletion after 10 minutes
            if persistent_files:
                schedule_file_deletion(persistent_files, delay_minutes=10)
                logger.info(f"Scheduled {len(persistent_files)} files for deletion after 10 minutes")

            # Generate PDF from analysis result
            pdf_title = f"Test Plan for {exam_type}" if exam_type else "Test Plan"

            # Log the analysis result for debugging
            logger.info(f"Test plan result status: {result.get('status')}")
            logger.info(f"Test plan contains content: {'Yes' if result.get('result') else 'No'}")

            # If there's no content in the result, log an error
            if not result.get("result"):
                logger.error("No content in test plan result. This should not happen with proper analysis.")

            pdf_path = generate_pdf_from_analysis(
                analysis_result=result,
                exam_type=exam_type,
                title=pdf_title
            )

            # Schedule PDF for deletion after 10 minutes
            schedule_file_deletion([pdf_path], delay_minutes=10)
            logger.info(f"Scheduled PDF for deletion after 10 minutes: {pdf_path}")

            # Return the PDF file
            return FileResponse(
                path=pdf_path,
                filename=os.path.basename(pdf_path),
                media_type="application/pdf"
            )

    except Exception as e:
        logger.error(f"Error generating PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")
