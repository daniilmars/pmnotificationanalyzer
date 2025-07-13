from fastapi import FastAPI, HTTPException
from app.services.analysis_service import analyze_text # <-- Angepasster Import
from app.models import AnalysisRequest, AnalysisResult

app = FastAPI(title="SAP PM Text Analyzer")

@app.post("/analyze", response_model=AnalysisResult)
def analyze(req: AnalysisRequest):
    try:
        result = analyze_text(req.text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))