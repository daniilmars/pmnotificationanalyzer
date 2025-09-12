from pydantic import BaseModel
from typing import List, Dict, Any

class AnalysisRequest(BaseModel):
    """The model for the incoming request."""
    text: str
    language: str = "en"

class Problem(BaseModel):
    title: str
    description: str
    fieldId: str
    hasSuggestion: bool

class AnalysisResponse(BaseModel):
    """The model for the outgoing response."""
    score: int
    problems: List[Problem]
    summary: str

class SuggestionRequest(BaseModel):
    notification: Dict[str, Any]
    problem: Problem
    language: str = "en"

class SuggestionResponse(BaseModel):
    suggestion: str