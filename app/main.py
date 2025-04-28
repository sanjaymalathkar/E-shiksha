import os
import uvicorn
import logging
from fastapi import FastAPI, Request, Response, HTTPException, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for the main app
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Mount static files for the landing page
app.mount("/landing-assets", StaticFiles(directory="landing-page/assets"), name="landing-assets")
app.mount("/landing-css", StaticFiles(directory="landing-page/css"), name="landing-css")
app.mount("/landing-js", StaticFiles(directory="landing-page/js"), name="landing-js")

# Configure templates
templates = Jinja2Templates(directory="app/templates")

# Import routers
from app.api.upload import router as upload_router
from app.api.analysis import router as analysis_router
from app.api.planner import router as planner_router
from app.api.folder_upload import router as folder_router
from app.api.maintenance import router as maintenance_router
from app.api.language import router as language_router, get_language
from app.api.mock_test import router as mock_test_router
from app.api.planner_local import router as planner_local_router
from app.api.study_plan import router as study_plan_router
from app.api.workflow import router as workflow_router

# Include routers
app.include_router(upload_router)
app.include_router(mock_test_router)
app.include_router(analysis_router)
app.include_router(planner_router)
app.include_router(planner_local_router)
app.include_router(folder_router)
app.include_router(maintenance_router)
app.include_router(language_router)
app.include_router(study_plan_router)
app.include_router(workflow_router)

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

@app.get("/pages/{page_name}")
async def landing_pages(page_name: str):
    """Serve landing page subpages"""
    file_path = f"landing-page/pages/{page_name}"
    if os.path.exists(file_path):
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Page not found")

@app.get("/app")
async def app_index(request: Request):
    """Serve the main application after login"""
    language = get_language(request)
    return templates.TemplateResponse("index.html", {"request": request, "language": language})

@app.get("/test-viewer")
async def test_viewer(request: Request):
    language = get_language(request)
    return templates.TemplateResponse("test_viewer.html", {"request": request, "language": language})

@app.get("/planner")
async def planner(request: Request):
    language = get_language(request)
    return templates.TemplateResponse("planner.html", {"request": request, "language": language})

@app.get("/daily-report")
async def daily_report(request: Request):
    language = get_language(request)
    return templates.TemplateResponse("daily_report.html", {"request": request, "language": language})

@app.get("/folder-upload")
async def folder_upload(request: Request):
    language = get_language(request)
    return templates.TemplateResponse("folder_upload.html", {"request": request, "language": language})

@app.get("/mock-test")
async def mock_test(request: Request):
    language = get_language(request)
    return templates.TemplateResponse("mock_test.html", {"request": request, "language": language})

@app.get("/study-plan")
async def study_plan(request: Request):
    language = get_language(request)
    return templates.TemplateResponse("study_plan.html", {"request": request, "language": language})

# Logout route
@app.get("/logout")
async def logout():
    """Log out the user and redirect to the landing page"""
    response = RedirectResponse(url="/")
    # Clear any cookies that might be used for authentication
    response.delete_cookie(key="session")
    response.delete_cookie(key="auth_token")
    response.delete_cookie(key="user_id")
    return response

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Startup event handler
@app.on_event("startup")
async def startup_event():
    logger.info("Starting background tasks")
    start_background_tasks()

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host=host, port=port, reload=True)
