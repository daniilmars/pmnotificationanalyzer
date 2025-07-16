from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
# Geänderte Imports, um die neuen, verschachtelten Modelle zu verwenden
from app.models import AnalysisCase, AnalysisResult
from app.services.analysis_service import analyze_text

app = FastAPI(title="SAP PM Text Analyzer")

# CORS-Middleware, die Anfragen vom Fiori-Frontend erlaubt
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Für die lokale Entwicklung am einfachsten
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    """
    Ein einfacher "Health Check"-Endpunkt, um zu prüfen, ob das Backend läuft.
    """
    return {"Status": "PM Analyzer Backend is running"}

@app.post("/analyze", response_model=AnalysisResult)
def analyze(req: AnalysisCase):
    """
    Nimmt eine vollständige "Akte" (AnalysisCase) entgegen und startet die
    ganzheitliche Analyse.
    """
    try:
        # Das gesamte "case"-Objekt wird an den Service weitergegeben
        result = analyze_text(case=req)
        return result
    except Exception as e:
        # Gibt detaillierte Fehler an das Frontend zurück
        raise HTTPException(status_code=500, detail=str(e))
