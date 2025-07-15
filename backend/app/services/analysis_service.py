import os
import re
import google.generativeai as genai # <-- Zurück zur Google-Bibliothek
from app.models import AnalysisResult

def analyze_text(text: str) -> AnalysisResult:
    """
    Analysiert einen SAP-Instandhaltungstext mit der Google Gemini API.
    """
    # API-Schlüssel aus der .env-Datei laden
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

        pattern = re.compile(
            r"Score:\s*(\d+)\s*Probleme:\s*(.*?)\s*Zusammenfassung:\s*(.*)",
            re.DOTALL | re.IGNORECASE
        )
        match = pattern.search(reply)

        if not match:
            raise ValueError(f"Konnte die Antwort von Gemini nicht parsen. Antwort war: {reply}")

        score = int(match.group(1).strip())
        issues_text = match.group(2).strip()
        issues = [line.strip("- ") for line in issues_text.split('\n') if line.strip() and line.strip().startswith('-')]
        summary = match.group(3).strip()

        return AnalysisResult(score=score, issues=issues, summary=summary)

    except Exception as e:
        print(f"Ein Fehler bei der Kommunikation mit der Google Gemini API ist aufgetreten: {e}")
        raise e