# /backend/app/models.py

from pydantic import BaseModel
from typing import List

class AnalysisRequest(BaseModel):
    """Das Modell für die eingehende Anfrage."""
    text: str

class AnalysisResponse(BaseModel):
    """Das Modell für die ausgehende Antwort."""
    score: int
    problems: List[str]
    summary: str