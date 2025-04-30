from pydantic import BaseModel
from typing import List, Dict, Any

class WorkflowStartResponse(BaseModel):
    status: str
    message: str
    topics: List[str]
    quiz: List[Dict[str, Any]]
