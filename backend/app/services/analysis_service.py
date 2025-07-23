import os
import re
import google.generativeai as genai # <-- Zurück zur Google-Bibliothek
from app.models import AnalysisResponse

def _parse_gemini_response(reply: str) -> AnalysisResponse:
    """
    Parses the raw text response from Gemini into a structured AnalysisResponse object.
    """
    pattern = re.compile(
        r"Score:\s*(\d+)\s*Probleme:\s*(.*?)\s*Zusammenfassung:\s*(.*)",
        re.DOTALL | re.IGNORECASE
    )
    match = pattern.search(reply)

    if not match:
        # In a real application, you might want to log the failed response for debugging.
        # import logging
        # logging.warning(f"Could not parse Gemini response: {reply}")
        raise ValueError(f"Konnte die Antwort von Gemini nicht parsen. Antwort war: {reply}")

    score = int(match.group(1).strip())
    issues_text = match.group(2).strip()
    # This list comprehension is effective for extracting bullet points.
    issues = [line.strip("- ") for line in issues_text.split('\n') if line.strip() and line.strip().startswith('-')]
    summary = match.group(3).strip()

    return AnalysisResponse(score=score, problems=issues, summary=summary)


def analyze_text(text: str) -> AnalysisResponse:
    """
    Analysiert einen SAP-Instandhaltungstext mit der Google Gemini API.
    """
    # Load API key from .env file
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GOOGLE_API_KEY environment variable is not set or could not be loaded.")
    genai.configure(api_key=api_key)

    # Der bewährte Prompt für Gemini
    prompt = f"""
    Du bist ein erfahrener GMP-Auditor und bewertest die Qualität von Instandhaltungsmeldungen in einem pharmazeutischen Produktionsbetrieb. Deine Bewertung muss extrem streng sein und sich an den Prinzipien von GMP und Datenintegrität (ALCOA+) orientieren.

    BEWERTUNGSMATRIX:
    - Score 90-100 (Audit-sicher): Alle 5 Säulen (GMP/ALCOA+, Rückverfolgbarkeit, Ursachenanalyse, Produkteinfluss, CAPA mit Vorbeugemassnahme) sind vollständig erfüllt. Alle IDs und Chargennummern sind vorhanden.
    - Score 70-89 (Gut, mit Lücken): Grösstenteils konform, aber es fehlt eine explizite Vorbeugemassnahme oder die Ursachenanalyse ist nicht tiefgehend.
    - Score 40-69 (Mangelhaft): Es fehlt eine klare Bewertung des Produkteinflusses oder die Ursachenanalyse. Kritische IDs (z.B. Chargennummer) fehlen.
    - Score 10-39 (Schwerwiegend mangelhaft): Mehrere Säulen fehlen. Die Rückverfolgbarkeit ist nicht gegeben.
    - Score 0-9 (Ungenügend): Der Eintrag ist für ein GMP-Umfeld völlig unbrauchbar.

    ANALYSIERE DIESEN TEXT:
    "{text}"

    GIB DEINE ANTWORT NUR IN DIESEM EXAKTEN FORMAT ZURÜCK, OHNE WEITERE ERKLÄRUNGEN:
    Score: <int>
    Probleme:
    - <Problem 1>
    - <Problem 2>
    Zusammenfassung: <String>
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        generation_config = genai.types.GenerationConfig(temperature=0.1)

        response = model.generate_content(prompt, generation_config=generation_config)
        reply = response.text
        
        return _parse_gemini_response(reply)

    except Exception as e:
        # It's good practice to log the error before re-raising it.
        print(f"Ein Fehler bei der Kommunikation mit der Google Gemini API ist aufgetreten: {e}")
        raise e