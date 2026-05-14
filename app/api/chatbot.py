import os
import json
import logging
import glob
import re
from typing import Dict, Any, List, Optional, Tuple
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
import asyncio
import requests
import google.generativeai as genai

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])

_PAR_BREAK = re.compile(r"\n\s*\n+")

def _split_paragraphs(text: str) -> List[str]:
    """Split document text into coarse paragraphs / blocks for retrieval."""
    if not text or not text.strip():
        return []
    parts = _PAR_BREAK.split(text.strip())
    out: List[str] = []
    for p in parts:
        block = " ".join(p.split())
        if len(block) < 40:
            continue
        out.append(block)
    if not out and text.strip():
        out.append(" ".join(text.strip().split()))
    return out


def _score_paragraph(p: str, terms: List[str]) -> int:
    low = p.lower()
    return sum(1 for t in terms if t in low)


def _best_paragraph_windows(
    text: str,
    terms: List[str],
    max_paragraphs: int = 8,
    window_chars: int = 2200,
) -> List[str]:
    """
    Pick paragraphs that match query terms; expand with neighboring paragraphs
    so answers can explain a full idea, not a single keyword hit.
    """
    paras = _split_paragraphs(text)
    if not paras:
        return []
    scores = [(i, _score_paragraph(p, terms)) for i, p in enumerate(paras)]
    hits = [i for i, s in scores if s > 0]
    if not hits:
        # fall back: use beginning of document
        joined = " ".join(paras[:3])
        return [joined[:window_chars]]

    windows: List[str] = []
    seen = set()
    for idx in sorted(hits, key=lambda i: scores[i][1], reverse=True)[:max_paragraphs]:
        lo = max(0, idx - 1)
        hi = min(len(paras), idx + 2)
        chunk = "\n\n".join(paras[lo:hi])
        if len(chunk) > window_chars:
            chunk = chunk[:window_chars] + "…"
        key = (lo, hi)
        if key in seen:
            continue
        seen.add(key)
        windows.append(chunk)
    return windows[:max_paragraphs]


def _build_context_from_corpus(
    corpus: List[Dict[str, str]],
    query: str,
    max_sources: int = 4,
) -> Tuple[str, List[Dict[str, Any]]]:
    """Select rich passages from uploaded files for the prompt."""
    raw_terms = [w for w in re.split(r"\s+", query.lower()) if len(w) > 2]
    terms = list(dict.fromkeys(raw_terms))[:24]
    if not terms:
        terms = [query.lower().strip()]

    scored_files: List[Tuple[int, Dict[str, str]]] = []
    for c in corpus:
        low = c["text"].lower()
        score = sum(1 for t in terms if t in low)
        scored_files.append((score, c))
    scored_files.sort(key=lambda x: x[0], reverse=True)

    blocks: List[str] = []
    sources: List[Dict[str, Any]] = []
    for score, c in scored_files[:max_sources]:
        if score == 0 and len(sources) > 0:
            continue
        wins = _best_paragraph_windows(c["text"], terms)
        if not wins:
            snippet = c["text"][:3200]
            wins = [snippet]
        combined = "\n\n---\n\n".join(wins)
        if len(combined) > 12000:
            combined = combined[:12000] + "…"
        blocks.append(f"[SOURCE: {c['file_name']}]\n{combined}")
        sources.append({"title": c["file_name"], "url": ""})

    return "\n\n".join(blocks), sources

class ChatbotRequest(BaseModel):
    message: str
    context: Optional[List[Dict[str, str]]] = None

class ChatbotResponse(BaseModel):
    response: str
    sources: Optional[List[Dict[str, Any]]] = None

@router.post("/query", response_model=ChatbotResponse)
async def query_chatbot(request: ChatbotRequest = Body(...)):
    """
    Answer strictly from uploaded content using Ollama.
    """
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        output_dir = os.path.join(base_dir, "data", "output")
        results_pattern = os.path.join(output_dir, "folder_results_*.json")
        result_files = sorted(glob.glob(results_pattern), key=os.path.getctime, reverse=True)
        if not result_files:
            raise HTTPException(status_code=404, detail="No uploaded content found")

        with open(result_files[0], "r", encoding="utf-8") as f:
            latest_results = json.load(f)

        corpus = []
        for item in latest_results:
            text = (item or {}).get("extracted_text", "").strip()
            if text and not text.startswith("Error:"):
                corpus.append({
                    "file_name": (item or {}).get("file_name", "unknown"),
                    "text": text
                })

        if not corpus:
            raise HTTPException(status_code=404, detail="No readable uploaded content found")

        context_block, sources = _build_context_from_corpus(corpus, request.message.strip())

        prompt = f"""You are a tutor helping a student using ONLY the passages below from their uploaded study materials.

Rules:
- Base your answer entirely on these passages. Do not invent facts or use outside knowledge.
- When the user mentions a keyword or topic, explain the full relevant idea: describe the complete argument or paragraph-level meaning found in the sources, not just a phrase.
- Use clear structure (short paragraphs or bullets). Quote or paraphrase closely from the material.
- If the passages do not contain enough information to answer, reply exactly: Not found in uploaded content.

User question:
{request.message}

Material:
{context_block}
"""

        model_name = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.15,
            "options": {"num_predict": 2048},
        }
        ollama_result = await asyncio.to_thread(
            lambda: requests.post("http://127.0.0.1:11434/api/generate", json=payload, timeout=120)
        )
        ollama_result.raise_for_status()
        answer_text = (ollama_result.json().get("response", "") or "").strip()
        if not answer_text:
            answer_text = "Not found in uploaded content."

        suspicious = (
            "contact the uploader",
            "cannot be used",
            "provided uploaded content only contains source",
            "i cannot",
            "as an ai language model",
        )
        if any(token in answer_text.lower() for token in suspicious):
            query_terms = [w.lower() for w in request.message.split() if len(w) > 2]
            fallback_blocks: List[str] = []
            for s in sources:
                fname = s.get("title") or ""
                block = next((c["text"] for c in corpus if c["file_name"] == fname), "")
                for para in _split_paragraphs(block)[:12]:
                    pl = para.lower()
                    if query_terms and any(t in pl for t in query_terms):
                        fallback_blocks.append(para)
            if fallback_blocks:
                answer_text = (
                    "Based on your uploaded material:\n\n"
                    + "\n\n".join(fallback_blocks[:4])
                )
            else:
                answer_text = "Not found in uploaded content."

        return {
            "response": answer_text,
            "sources": sources
        }
    except HTTPException:
        raise
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
