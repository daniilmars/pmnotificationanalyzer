from pydantic import BaseModel
from typing import List

class AnalysisRequest(BaseModel):
    """The model for the incoming request."""
    text: str
    language: str = "en" # Add this line

class AnalysisResponse(BaseModel):
    """The model for the outgoing response."""
    score: int
    problems: List[str]
    summary: str