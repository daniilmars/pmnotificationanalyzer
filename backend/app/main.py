from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.services.analysis_service import analyze_text
from app.models import AnalysisRequest, AnalysisResult

app = FastAPI(title="SAP PM Text Analyzer")

# CORS-Middleware, die explizit jede Herkunft erlaubt
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# NEU: Ein einfacher "Health Check"-Endpunkt
@app.get("/")
def read_root():
    return {"Status": "PM Analyzer Backend is running"}

@app.post("/analyze", response_model=AnalysisResult)
def analyze(req: AnalysisRequest):
    try:
        result = analyze_text(req.text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))