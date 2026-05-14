import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Body, UploadFile, File
from pydantic import BaseModel
import google.generativeai as genai

# RAG utilities (file-based offline AI tutor)
from app.utils import pdf_processor, retriever, ai_tutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])

# Folder where uploaded study material is persisted on disk.
# Resolved relative to the project root so it works in dev and Docker.
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
UPLOAD_DIR = os.path.join(_PROJECT_ROOT, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class ChatbotRequest(BaseModel):
    # `message` is the student question; `mode` selects the response style
    # (normal / simple / example / exam / summary). `context` is kept for
    # backwards compatibility with the old chatbot UI.
    message: str
    mode: Optional[str] = "normal"
    context: Optional[List[Dict[str, str]]] = None

class ChatbotResponse(BaseModel):
    response: str
    sources: Optional[List[Dict[str, Any]]] = None


@router.post("/upload")
async def upload_study_material(file: UploadFile = File(...)):
    """
    Upload a single PDF or TXT file to be used as the chatbot's knowledge
    source. The file is:
      1. saved under uploads/
      2. text-extracted (PyMuPDF for PDF, plain read for TXT)
      3. cleaned and split into ~500-word chunks (100-word overlap)
      4. added to the in-memory TF-IDF retriever index
    """
    filename = file.filename or "upload.bin"
    if not pdf_processor.is_allowed_file(filename):
        raise HTTPException(
            status_code=400,
            detail="Only .pdf and .txt files are allowed.",
        )

    save_path = os.path.join(UPLOAD_DIR, filename)
    try:
        # Stream the upload to disk so we don't blow up memory on big PDFs.
        with open(save_path, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except Exception as e:
        logger.error("Failed to save upload %s: %s", filename, e)
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")

    # Extract + clean + chunk (CPU-bound, run in a thread).
    try:
        file_name, chunks = await asyncio.to_thread(
            pdf_processor.process_file, save_path
        )
    except RuntimeError as e:
        # PyMuPDF missing -> friendly error
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("Extraction failed for %s: %s", filename, e)
        raise HTTPException(
            status_code=400,
            detail=f"Could not read the uploaded file: {e}",
        )

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="No readable text was found inside the uploaded file.",
        )

    n_added = retriever.add_file(file_name, chunks)
    return {
        "status": "success",
        "file_name": file_name,
        "chunks": n_added,
        "files_indexed": retriever.list_files(),
        "message": f"Uploaded '{file_name}' and indexed {n_added} chunks.",
    }


@router.post("/clear")
async def clear_study_material():
    """Forget every uploaded file (also removes them from disk)."""
    retriever.clear()
    # Best-effort disk cleanup; do not fail the API if files are locked.
    try:
        for fname in os.listdir(UPLOAD_DIR):
            fp = os.path.join(UPLOAD_DIR, fname)
            if os.path.isfile(fp):
                os.remove(fp)
    except Exception as e:
        logger.warning("Could not clean uploads dir: %s", e)
    return {"status": "success", "message": "Uploaded material cleared."}


@router.post("/query", response_model=ChatbotResponse)
async def query_chatbot(request: ChatbotRequest = Body(...)):
    """
    Strict RAG flow:
      1. Reject if nothing has been uploaded.
      2. Retrieve top chunks via TF-IDF + cosine similarity.
      3. Reject if best similarity is below threshold.
      4. Build the strict E-Shiksha tutor prompt with the chosen response mode.
      5. Dispatch to the AI backend selected by AI_MODE
         (default 'ollama' -> local llama3.2:3b; 'online' -> Gemini if a key
         is configured). Fall back gracefully if the backend is unavailable.
      6. Validate the answer against the retrieved context to catch any
         out-of-context drift; replace with NOT_IN_MATERIAL_MESSAGE if so.
    """
    question = (request.message or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    # 1. Nothing uploaded yet.
    if not retriever.has_content():
        return {"response": ai_tutor.NO_FILE_MESSAGE, "sources": []}

    # 2. Retrieve top relevant chunks (top 4 by default).
    top_chunks, top_sources, best_sim = retriever.retrieve(question, top_k=4)

    # 3. Hallucination guard: if even the best match is weak, refuse.
    if not top_chunks or best_sim < retriever.SIMILARITY_THRESHOLD:
        return {
            "response": ai_tutor.NOT_IN_MATERIAL_MESSAGE,
            "sources": [],
        }

    # 4. Build prompt with the strict tutor rules + chosen response mode.
    prompt = ai_tutor.build_prompt(top_chunks, question, request.mode or "normal")

    # 5. Dispatch to the configured backend in a thread (network I/O).
    answer_text, unavailable_msg = await asyncio.to_thread(
        ai_tutor.generate_answer, prompt
    )
    if not answer_text:
        return {"response": unavailable_msg, "sources": []}

    # 6. Validate that the model stayed inside the retrieved context.
    is_valid, reason = ai_tutor.validate_answer(answer_text, top_chunks)
    if not is_valid:
        logger.info("Answer rejected by validator: %s", reason)
        return {"response": ai_tutor.NOT_IN_MATERIAL_MESSAGE, "sources": []}

    # Deduplicate source filenames while preserving order.
    seen = set()
    sources: List[Dict[str, Any]] = []
    for s in top_sources:
        if s in seen:
            continue
        seen.add(s)
        sources.append({"title": s, "url": "", "score": round(best_sim, 3)})

    return {"response": answer_text, "sources": sources}

@router.post("/education-resources")
async def get_education_resources(topic: str = Body(..., embed=True)):
    """
    Get educational resources for a specific topic using Google Gemini API
    """
    try:
        # Configure Google Gemini API
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GOOGLE_API_KEY environment variable not set")

        genai.configure(api_key=api_key)

        # Initialize model
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Prepare the prompt
        prompt = f"""
        Provide a comprehensive list of high-quality educational resources for the topic: {topic}
        
        Include:
        1. Books and textbooks
        2. Online courses
        3. Websites and learning platforms
        4. YouTube channels and video resources
        5. Practice materials and question banks
        
        For each resource, provide:
        - Name/title
        - Brief description
        - Why it's valuable for students
        
        Format the output as a structured JSON with categories and resources.
        """

        # Generate response
        response = await asyncio.to_thread(
            lambda: model.generate_content(prompt)
        )

        # Try to parse as JSON
        try:
            resources = json.loads(response.text)
            return resources
        except json.JSONDecodeError:
            # Return as text if not valid JSON
            return {
                "resources": response.text.strip(),
                "format": "text"
            }
    except Exception as e:
        logger.error(f"Error getting educational resources: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
