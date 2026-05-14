import os
import uvicorn
import logging
from fastapi import FastAPI, Request, Response, HTTPException, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Run database migrations
try:
    from app.core.migrations.add_pgvector import run_migrations
    if run_migrations():
        logger.info("Database migrations completed successfully")
    else:
        logger.warning("Database migrations failed, some features may not work properly")
except Exception as e:
    logger.error(f"Error running database migrations: {str(e)}")

# Create FastAPI app
app = FastAPI(
    title="Educational Content Analysis System",
    description="AI-powered system for analyzing educational content and generating test plans",
    version="0.1.0",
)

# Import background tasks
from app.core.tasks import start_background_tasks
from app.core.scheduled_tasks import run_scheduled_tasks
from app.auth.firebase_auth import init_firebase_admin
import asyncio

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SECRET_KEY", "your-secret-key-for-sessions"),
    max_age=60 * 60 * 24  # 1 day in seconds
)

# Mount static files for the main app
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Mount static files for the landing page
app.mount("/landing-assets", StaticFiles(directory="landing-page/assets"), name="landing-assets")
app.mount("/landing-css", StaticFiles(directory="landing-page/css"), name="landing-css")
app.mount("/landing-js", StaticFiles(directory="landing-page/js"), name="landing-js")
app.mount("/js", StaticFiles(directory="landing-page/js"), name="js")
# Create a custom route for the contact-form.js file
@app.get("/contact-form.js")
async def contact_form_js():
    return FileResponse("landing-page/contact-form.js")

# Configure templates
templates = Jinja2Templates(directory="app/templates")

# Import routers
from app.api.upload import router as upload_router
from app.api.analysis import router as analysis_router
from app.api.planner import router as planner_router
from app.api.folder_upload import router as folder_router
from app.api.maintenance import router as maintenance_router
from app.api.language import router as language_router, get_language
from app.api.planner_local import router as planner_local_router
from app.api.study_plan import router as study_plan_router
from app.api.workflow import router as workflow_router
from app.api.contact import router as contact_router
from app.api.user import router as user_router
from app.routes.user_files import router as user_files_router
from app.api.domain_test import router as domain_test_router
from app.api.attendance import router as attendance_router
from app.api.daily_email import router as daily_email_router
from app.api.firebase_auth import router as firebase_auth_router
from app.api.ollama_processing import router as ollama_processing_router
from app.api.direct_user_create import router as direct_user_create_router
from app.api.direct_user_login import router as direct_user_login_router
from app.api.user_tracking import router as user_tracking_router
from app.api.chatbot import router as chatbot_router
from app.api.mock_test import router as mock_test_router
from app.api.tutor import router as tutor_router   # Unified AI Tutor workflow

# Include routers
app.include_router(upload_router)
app.include_router(analysis_router)
app.include_router(planner_router)
app.include_router(planner_local_router)
app.include_router(folder_router)
app.include_router(maintenance_router)
app.include_router(language_router)
app.include_router(study_plan_router)
app.include_router(workflow_router)
app.include_router(user_files_router)
app.include_router(contact_router)
app.include_router(user_router)
app.include_router(domain_test_router, prefix="/api/domain-test")
app.include_router(attendance_router, prefix="/api/attendance")
app.include_router(daily_email_router)
app.include_router(firebase_auth_router)
app.include_router(ollama_processing_router, prefix="/api/ollama")
app.include_router(direct_user_create_router)
app.include_router(direct_user_login_router)
app.include_router(user_tracking_router)
app.include_router(chatbot_router)
app.include_router(mock_test_router)
app.include_router(tutor_router)          # Unified AI Tutor workflow

# Middleware to add language context to all templates
@app.middleware("http")
async def add_language_context(request: Request, call_next):
    response = await call_next(request)
    return response

# Page routes
@app.get("/")
async def root():
    """Serve the landing page"""
    return FileResponse("landing-page/index.html")

@app.get("/landing")
async def landing():
    """Serve the landing page"""
    return FileResponse("landing-page/index.html")

@app.get("/pages/{page_name}")
async def landing_pages(page_name: str):
    """Serve landing page subpages"""
    file_path = f"landing-page/pages/{page_name}"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Page not found")

# All other page routes have been removed to use only the landing page

@app.get("/app")
async def app_index():
    """
    Legacy /app route — redirect to the unified AI Tutor dashboard.
    This merges the old Dashboard and AI Tutor into one page.
    """
    return RedirectResponse(url="/tutor", status_code=302)

@app.get("/tutor")
async def tutor_page(request: Request):
    """
    Serve the unified AI Tutor workflow page:
    Upload → Analyse → Profile → Calendar Study Plan → Chatbot
    """
    language = get_language(request)
    try:
        user_data = {
            "username": request.session.get("username", ""),
            "email":    request.session.get("email", ""),
            "phone":    request.session.get("phone", ""),
            "user_id":  request.session.get("user_id", ""),
        }
    except Exception:
        user_data = {"username": "", "email": "", "phone": "", "user_id": ""}
    return templates.TemplateResponse(
        "tutor.html",
        {"request": request, "language": language, "user": user_data}
    )


@app.get("/planner")
async def planner():
    """
    Planner is now part of the unified AI Tutor dashboard.
    Redirect here so old bookmarks and nav links still work.
    The planner auto-generates after file upload on the /tutor page.
    """
    return RedirectResponse(url="/tutor#card-plan", status_code=302)

@app.get("/daily-report")
async def daily_report(request: Request):
    """Serve the daily report page"""
    language = get_language(request)

    # Get user data from session if available
    try:
        user_data = {
            "username": request.session.get("username", ""),
            "email": request.session.get("email", ""),
            "phone": request.session.get("phone", ""),
            "user_id": request.session.get("user_id", "")
        }
    except Exception as e:
        logger.error(f"Error accessing session: {str(e)}")
        user_data = {
            "username": "",
            "email": "",
            "phone": "",
            "user_id": ""
        }

    return templates.TemplateResponse(
        "daily_report.html",
        {
            "request": request,
            "language": language,
            "user": user_data
        }
    )

@app.get("/study-plan")
async def study_plan(request: Request):
    """Serve the study plan page"""
    language = get_language(request)

    # Get user data from session if available
    try:
        user_data = {
            "username": request.session.get("username", ""),
            "email": request.session.get("email", ""),
            "phone": request.session.get("phone", ""),
            "user_id": request.session.get("user_id", "")
        }
    except Exception as e:
        logger.error(f"Error accessing session: {str(e)}")
        user_data = {
            "username": "",
            "email": "",
            "phone": "",
            "user_id": ""
        }

    return templates.TemplateResponse(
        "study_plan.html",
        {
            "request": request,
            "language": language,
            "user": user_data
        }
    )

@app.get("/test-viewer")
async def test_viewer(request: Request):
    """Serve the test viewer page"""
    language = get_language(request)

    # Get user data from session if available
    try:
        user_data = {
            "username": request.session.get("username", ""),
            "email": request.session.get("email", ""),
            "phone": request.session.get("phone", ""),
            "user_id": request.session.get("user_id", "")
        }
    except Exception as e:
        logger.error(f"Error accessing session: {str(e)}")
        user_data = {
            "username": "",
            "email": "",
            "phone": "",
            "user_id": ""
        }

    return templates.TemplateResponse(
        "test_viewer.html",
        {
            "request": request,
            "language": language,
            "user": user_data
        }
    )

@app.get("/folder-upload")
async def folder_upload(request: Request):
    """Serve the folder upload page"""
    language = get_language(request)

    # Get user data from session if available
    try:
        user_data = {
            "username": request.session.get("username", ""),
            "email": request.session.get("email", ""),
            "phone": request.session.get("phone", ""),
            "user_id": request.session.get("user_id", "")
        }
    except Exception as e:
        logger.error(f"Error accessing session: {str(e)}")
        user_data = {
            "username": "",
            "email": "",
            "phone": "",
            "user_id": ""
        }

    return templates.TemplateResponse(
        "folder_upload.html",
        {
            "request": request,
            "language": language,
            "user": user_data
        }
    )



# Logout route
@app.get("/logout")
async def logout():
    """Log out the user and redirect to the landing page"""
    # Create a response that redirects to the landing page with status code 303
    response = RedirectResponse(url="/", status_code=303)
    # Clear any cookies that might be used for authentication
    response.delete_cookie(key="session")
    response.delete_cookie(key="auth_token")
    response.delete_cookie(key="user_id")
    return response

# Mock Test — now integrated into the unified /tutor dashboard.
# Redirect so old nav links still work.
@app.get("/mock-test")
async def mock_test():
    """
    Mock Test is now part of the unified AI Tutor dashboard.
    It generates questions from the uploaded PDF (not hardcoded JEE/GATE/KCET).
    Redirect to /tutor so users land on the correct page.
    """
    return RedirectResponse(url="/tutor#card-mock-test", status_code=302)

# Domain Test route - Actual Test
@app.get("/domain-test/{domain}")
async def domain_test(request: Request, domain: str):
    """Serve the domain test page for a specific domain"""
    language = get_language(request)

    # Get user data from session if available
    try:
        user_data = {
            "username": request.session.get("username", ""),
            "email": request.session.get("email", ""),
            "phone": request.session.get("phone", ""),
            "user_id": request.session.get("user_id", "")
        }
    except Exception as e:
        logger.error(f"Error accessing session: {str(e)}")
        user_data = {
            "username": "",
            "email": "",
            "phone": "",
            "user_id": ""
        }

    return templates.TemplateResponse(
        "domain_test.html",
        {
            "request": request,
            "language": language,
            "user": user_data,
            "domain": domain
        }
    )

# Attendance route
@app.get("/attendance")
async def attendance(request: Request):
    """Serve the attendance page"""
    language = get_language(request)

    # Get user data from session if available
    try:
        user_data = {
            "username": request.session.get("username", ""),
            "email": request.session.get("email", ""),
            "phone": request.session.get("phone", ""),
            "user_id": request.session.get("user_id", "")
        }
    except Exception as e:
        logger.error(f"Error accessing session: {str(e)}")
        user_data = {
            "username": "",
            "email": "",
            "phone": "",
            "user_id": ""
        }

    return templates.TemplateResponse(
        "attendance.html",
        {
            "request": request,
            "language": language,
            "user": user_data
        }
    )

# Daily Email Testing route
@app.get("/daily-email")
async def daily_email(request: Request):
    """Serve the daily email testing page"""
    language = get_language(request)

    # Get user data from session if available
    try:
        user_data = {
            "username": request.session.get("username", ""),
            "email": request.session.get("email", ""),
            "phone": request.session.get("phone", ""),
            "user_id": request.session.get("user_id", "")
        }
    except Exception as e:
        logger.error(f"Error accessing session: {str(e)}")
        user_data = {
            "username": "",
            "email": "",
            "phone": "",
            "user_id": ""
        }

    return templates.TemplateResponse(
        "daily_email.html",
        {
            "request": request,
            "language": language,
            "user": user_data
        }
    )

# Profile route
@app.get("/profile")
async def profile(request: Request):
    """Serve the user profile page"""
    language = get_language(request)

    # Get user data from session if available
    try:
        user_data = {
            "username": request.session.get("username", ""),
            "email": request.session.get("email", ""),
            "phone": request.session.get("phone", ""),
            "user_id": request.session.get("user_id", "")
        }
    except Exception as e:
        logger.error(f"Error accessing session: {str(e)}")
        user_data = {
            "username": "",
            "email": "",
            "phone": "",
            "user_id": ""
        }

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "language": language,
            "user": user_data
        }
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Startup event handler
@app.on_event("startup")
async def startup_event():
    # Initialize Firebase Admin SDK
    logger.info("Initializing Firebase Admin SDK")
    init_firebase_admin()

    # Start background tasks
    logger.info("Starting background tasks")
    start_background_tasks()

    # Start scheduled tasks for attendance tracking
    logger.info("Starting attendance tracking tasks")
    asyncio.create_task(run_scheduled_tasks())

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
