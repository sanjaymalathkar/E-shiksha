from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class Attendance(BaseModel):
    """MongoDB attendance model"""
    user_id: str  # Firebase UID
    date: datetime = Field(default_factory=lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
    status: str = "present"  # "present" or "absent"
    login_time: Optional[datetime] = None
    logout_time: Optional[datetime] = None
    
    class Config:
        arbitrary_types_allowed = True

class AttendanceRecord(BaseModel):
    """Model for attendance records"""
    user_id: str
    username: str
    email: str
    attendance: List[Dict[str, Any]]
    absent_days: int = 0
    present_days: int = 0
    streak: int = 0  # Consecutive days present
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True
