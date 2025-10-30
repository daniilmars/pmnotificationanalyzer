from pydantic import BaseModel
from typing import List, Optional

class AnalysisRequest(BaseModel):
    """The model for the incoming request."""
    text: str
    language: str = "en"

class ProblemDetail(BaseModel):
    """Describes a single problem with a link to a field."""
    field: Optional[str] = None
    description: str

class AnalysisResponse(BaseModel):
    """The model for the outgoing response."""
    score: int
    problems: List[ProblemDetail]
    summary: str
