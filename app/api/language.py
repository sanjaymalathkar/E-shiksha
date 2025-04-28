from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import RedirectResponse
from typing import Optional
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["language"])

@router.get("/api/language/{lang}")
async def set_language(
    lang: str,
    request: Request,
    redirect: Optional[str] = None
):
    """
    Set the language for the user session
    
    Args:
        lang: Language code (en, hi, kn)
        redirect: URL to redirect to after setting language
        
    Returns:
        Redirect response with language cookie set
    """
    # Validate language code
    valid_languages = ["en", "hi", "kn"]
    if lang not in valid_languages:
        lang = "en"  # Default to English if invalid
    
    # Get redirect URL or default to home page
    redirect_url = redirect or request.headers.get("referer") or "/"
    
    # Create response with redirect
    response = RedirectResponse(url=redirect_url)
    
    # Set language cookie (expires in 1 year)
    response.set_cookie(
        key="language",
        value=lang,
        max_age=31536000,  # 1 year in seconds
        httponly=True,
        samesite="lax"
    )
    
    logger.info(f"Language set to {lang}, redirecting to {redirect_url}")
    return response

# Function to get current language from request
def get_language(request: Request) -> str:
    """
    Get the current language from cookies or default to English
    
    Args:
        request: FastAPI request object
        
    Returns:
        Language code (en, hi, kn)
    """
    return request.cookies.get("language", "en")
