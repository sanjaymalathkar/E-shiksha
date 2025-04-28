import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, StreamingResponse
import firebase_admin
from firebase_admin import auth, credentials
from pydantic import BaseModel

from app.core.mongodb import save_file, get_file, get_file_metadata, delete_file, get_user_files

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK if not already initialized
try:
    firebase_app = firebase_admin.get_app()
except ValueError:
    # Use service account credentials if available, otherwise use default credentials
    cred_path = os.getenv("FIREBASE_CREDENTIALS")
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        cred = credentials.ApplicationDefault()
    
    firebase_app = firebase_admin.initialize_app(cred)

# Create router
router = APIRouter(
    prefix="/api/user-files",
    tags=["user-files"],
    responses={404: {"description": "Not found"}},
)

# Models
class FileResponse(BaseModel):
    file_id: str
    filename: str
    content_type: str
    size: int
    upload_date: datetime
    user_id: str

class FileListResponse(BaseModel):
    files: List[FileResponse]
    count: int

# Helper function to verify Firebase ID token
async def verify_firebase_token(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Verify Firebase ID token from Authorization header
    
    Args:
        authorization: Authorization header value
    
    Returns:
        Firebase user claims
    
    Raises:
        HTTPException: If token is invalid or missing
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        logger.error(f"Error verifying Firebase token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid authentication token")

@router.post("/upload", response_model=FileResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    description: str = Form(""),
    user_claims: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    Upload a file and store it in MongoDB GridFS
    
    Args:
        request: FastAPI request object
        file: Uploaded file
        description: Optional file description
        user_claims: Firebase user claims from token verification
    
    Returns:
        File metadata
    """
    try:
        # Get user ID from Firebase token
        user_id = user_claims.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user ID in token")
        
        # Read file content
        file_content = await file.read()
        
        # Create metadata
        metadata = {
            "user_id": user_id,
            "description": description,
            "original_filename": file.filename,
            "upload_ip": request.client.host if request.client else None,
            "upload_time": datetime.now().isoformat()
        }
        
        # Save file to GridFS
        file_id = save_file(
            file_data=file_content,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            metadata=metadata
        )
        
        # Get file metadata
        file_metadata = get_file_metadata(file_id)
        
        if not file_metadata:
            raise HTTPException(status_code=500, detail="Failed to retrieve file metadata")
        
        # Return response
        return FileResponse(
            file_id=file_id,
            filename=file_metadata["filename"],
            content_type=file_metadata["content_type"],
            size=file_metadata["length"],
            upload_date=file_metadata["upload_date"],
            user_id=user_id
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

@router.get("/list", response_model=FileListResponse)
async def list_files(
    user_claims: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    List all files for the authenticated user
    
    Args:
        user_claims: Firebase user claims from token verification
    
    Returns:
        List of file metadata
    """
    try:
        # Get user ID from Firebase token
        user_id = user_claims.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user ID in token")
        
        # Get files for user
        user_files = get_user_files(user_id)
        
        # Format response
        files = []
        for file in user_files:
            files.append(FileResponse(
                file_id=file["file_id"],
                filename=file["filename"],
                content_type=file["content_type"],
                size=file["length"],
                upload_date=file["upload_date"],
                user_id=user_id
            ))
        
        return FileListResponse(
            files=files,
            count=len(files)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

@router.get("/download/{file_id}")
async def download_file(
    file_id: str,
    user_claims: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    Download a file from GridFS
    
    Args:
        file_id: ID of the file to download
        user_claims: Firebase user claims from token verification
    
    Returns:
        File content as streaming response
    """
    try:
        # Get user ID from Firebase token
        user_id = user_claims.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user ID in token")
        
        # Get file metadata
        file_metadata = get_file_metadata(file_id)
        
        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Check if user owns the file
        if file_metadata.get("metadata", {}).get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="You don't have permission to access this file")
        
        # Get file content
        file_content = get_file(file_id)
        
        if not file_content:
            raise HTTPException(status_code=404, detail="File content not found")
        
        # Return file as streaming response
        def iterfile():
            yield file_content
        
        return StreamingResponse(
            iterfile(),
            media_type=file_metadata["content_type"],
            headers={
                "Content-Disposition": f"attachment; filename=\"{file_metadata['filename']}\""
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

@router.delete("/{file_id}")
async def delete_user_file(
    file_id: str,
    user_claims: Dict[str, Any] = Depends(verify_firebase_token)
):
    """
    Delete a file from GridFS
    
    Args:
        file_id: ID of the file to delete
        user_claims: Firebase user claims from token verification
    
    Returns:
        Success message
    """
    try:
        # Get user ID from Firebase token
        user_id = user_claims.get("uid")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid user ID in token")
        
        # Get file metadata
        file_metadata = get_file_metadata(file_id)
        
        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Check if user owns the file
        if file_metadata.get("metadata", {}).get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="You don't have permission to delete this file")
        
        # Delete file
        success = delete_file(file_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete file")
        
        return {"message": "File deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")
