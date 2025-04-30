from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class User(BaseModel):
    """User model for the application"""
    
    id: Optional[int] = None
    firebase_uid: str
    username: str
    email: str
    display_name: Optional[str] = None
    role: str = "student"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        arbitrary_types_allowed = True
