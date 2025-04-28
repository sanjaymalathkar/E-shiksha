from pydantic import BaseModel
from typing import List
from app.models.mock_test import MockTestQuestion

class WorkflowStartResponse(BaseModel):
    status: str
    message: str
    topics: List[str]
    quiz: List[MockTestQuestion]
