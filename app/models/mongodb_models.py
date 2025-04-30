from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class MongoDBUser(BaseModel):
    """MongoDB user model"""
    firebase_uid: str
    username: str
    email: str
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    mobile_number: Optional[str] = None
    password_hash: str  # Hashed password for local authentication (now required)
    role: str  # 'student' or 'teacher'
    last_login: Optional[datetime] = None  # Last login timestamp
    last_login_ip: Optional[str] = None  # Last login IP address
    login_count: int = 0  # Number of logins
    email_verified: bool = False  # Whether the email has been verified
    account_disabled: bool = False  # Whether the account is disabled
    auth_provider: str = "email"  # Authentication provider (email, google, etc.)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        arbitrary_types_allowed = True

class UserFile(BaseModel):
    """User file model for MongoDB"""
    file_id: str
    user_id: str  # Firebase UID
    filename: str
    content_type: str
    size: int
    upload_date: datetime
    exam_type: Optional[str] = None
    tags: List[str] = []
    metadata: Dict[str, Any] = {}

    class Config:
        arbitrary_types_allowed = True

class UserFileCreate(BaseModel):
    """Model for creating a new user file"""
    filename: str
    content_type: str
    exam_type: Optional[str] = None
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
