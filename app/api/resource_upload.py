import os
import shutil
import json
import logging
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.core.ocr.processor import process_file
from app.core.ollama_local import run_ollama_json
from app.core.analysis.text_analyzer import analyze_text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/resource",
    tags=["resource"],
    responses={404: {"description": "Not found"}},
)

class ResourceAnalysisResponse(BaseModel):
    status: str
    message: str
    resource_id: str
    topics: List[str]
    content_summary: str
    ready_for_quiz: bool

@router.post("/upload", response_model=ResourceAnalysisResponse)
async def upload_resource(
    request: Request,
    file: UploadFile = File(...),
):
    """
    Upload and analyze a resource file.
    The file is processed immediately to extract topics and content for quiz generation.
    """
    try:
        # Create resource folder if it doesn't exist
        resource_folder = os.path.join("data", "resources")
        os.makedirs(resource_folder, exist_ok=True)

        # Generate a unique resource ID
        resource_id = f"resource_{os.urandom(4).hex()}"

        # Create a folder for this resource
        resource_path = os.path.join(resource_folder, resource_id)
        os.makedirs(resource_path, exist_ok=True)

        # Save the uploaded file
        file_path = os.path.join(resource_path, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Process the file to extract text
        file_result = await process_file(file_path)

        # Extract text content
        text_content = file_result.get("full_text", "")

        # Analyze the text to extract topics and other information
        analysis_result = await analyze_text(text_content)

        # Generate a content summary using Ollama
        summary_prompt = f"""
        Provide a concise summary of the following educational content.
        Focus on the main topics, key concepts, and learning objectives.
        Keep the summary under 200 words.

        Content:
        {text_content[:4000]}  # Limit content length to avoid token limits

        Return your response as a JSON object with a single key "summary" containing the summary text.
        """

        try:
            summary_result = run_ollama_json(summary_prompt, model="llama3")
            content_summary = summary_result.get("summary", "")
            if not content_summary or not isinstance(content_summary, str):
                # Try to extract summary from raw text if JSON parsing failed
                if isinstance(summary_result, dict) and "raw" in summary_result:
                    raw_text = summary_result["raw"]
                    # Extract text between the first and last paragraph
                    lines = [line for line in raw_text.split('\n') if line.strip()]
                    if lines:
                        content_summary = '\n'.join(lines)
                    else:
                        content_summary = "Content summary not available."
                else:
                    content_summary = "Content summary not available."
        except Exception as e:
            logger.error(f"Error generating content summary: {str(e)}")
            content_summary = "Error generating content summary."

        # Save the analysis result
        analysis_file = os.path.join(resource_path, "analysis.json")
        with open(analysis_file, "w", encoding="utf-8") as f:
            json.dump({
                "resource_id": resource_id,
                "file_name": file.filename,
                "file_path": file_path,
                "topics": analysis_result.get("topics", []),
                "keywords": analysis_result.get("keywords", []),
                "content_summary": content_summary,
                "full_text": text_content
            }, f, ensure_ascii=False, indent=2)

        return ResourceAnalysisResponse(
            status="success",
            message="Resource uploaded and analyzed successfully",
            resource_id=resource_id,
            topics=analysis_result.get("topics", []),
            content_summary=content_summary,
            ready_for_quiz=True
        )
    except Exception as e:
        logger.error(f"Error processing resource: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
