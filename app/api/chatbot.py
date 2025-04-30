import os
import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
import google.generativeai as genai
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])

class ChatbotRequest(BaseModel):
    message: str
    context: Optional[List[Dict[str, str]]] = None

class ChatbotResponse(BaseModel):
    response: str
    sources: Optional[List[Dict[str, Any]]] = None

@router.post("/query", response_model=ChatbotResponse)
async def query_chatbot(request: ChatbotRequest = Body(...)):
    """
    Process a chatbot query using Google Gemini API
    """
    try:
        # Configure Google Gemini API
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="GOOGLE_API_KEY environment variable not set")

        genai.configure(api_key=api_key)

        # Initialize model
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Prepare the prompt with educational focus
        prompt = f"""
        You are an educational assistant specializing in competitive exams like JEE, GMAT, UPSC, CAT, GATE, and NEET.
        
        Provide helpful, accurate, and educational information in response to the following query.
        Focus on providing factual information, study tips, and resources related to education.
        
        If the query is about a specific exam, provide detailed information about that exam.
        If the query is about study techniques, provide evidence-based advice.
        If the query is about educational resources, recommend high-quality sources.
        
        User query: {request.message}
        """

        # Add context if provided
        if request.context:
            context_text = "\n\n".join([f"{item.get('role', 'Context')}: {item.get('content', '')}" for item in request.context])
            prompt += f"\n\nAdditional context:\n{context_text}"

        # Generate response
        response = await asyncio.to_thread(
            lambda: model.generate_content(prompt)
        )

        # Extract educational sources
        sources = []
        try:
            # Try to extract sources from the response
            response_text = response.text.strip()
            
            # Look for sources section
            if "Sources:" in response_text:
                main_content, sources_text = response_text.split("Sources:", 1)
                response_text = main_content.strip()
                
                # Parse sources
                source_lines = sources_text.strip().split("\n")
                for line in source_lines:
                    if line.strip():
                        sources.append({"title": line.strip(), "url": ""})
            
            # If no explicit sources but references are detected
            elif "Reference:" in response_text or "References:" in response_text:
                for marker in ["Reference:", "References:"]:
                    if marker in response_text:
                        parts = response_text.split(marker, 1)
                        response_text = parts[0].strip()
                        refs = parts[1].strip().split("\n")
                        for ref in refs:
                            if ref.strip():
                                sources.append({"title": ref.strip(), "url": ""})
                        break
        except Exception as e:
            logger.warning(f"Error extracting sources: {str(e)}")
            # Continue without sources if extraction fails
        
        return {
            "response": response.text.strip(),
            "sources": sources
        }
    except Exception as e:
        logger.error(f"Error in chatbot query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
