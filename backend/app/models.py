from pydantic import BaseModel

class AnalysisRequest(BaseModel):
    text: str

class AnalysisResult(BaseModel):
    score: int
    issues: list[str]
    summary: str
    