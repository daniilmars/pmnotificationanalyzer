import os
import re
import google.generativeai as genai
from app.models import AnalysisResult

def analyze_text(text: str) -> AnalysisResult:
    """
    Analysiert einen SAP-Instandhaltungstext mit Google Gemini und extrahiert strukturierte Daten.
    Die API-Konfiguration erfolgt bei jedem Aufruf, um das Laden von Umgebungsvariablen sicherzustellen.
    """
    # --- API Key Configuration ---
    # This block is now inside the function to ensure .env is loaded first.
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GOOGLE_API_KEY environment variable is not set or could not be loaded.")
    genai.configure(api_key=api_key)
    # --------------------------------

    # Dieser Prompt ist optimiert, um Gemini zur strikten Einhaltung des Formats anzuleiten.
    prompt = f"""
    Analysiere folgenden SAP-Instandhaltungstext:
    "{text}"

    1. Bewerte den Text auf Vollständigkeit (Ursache, Maßnahme, Klarheit).
    2. Gib eine Punktzahl von 0 bis 100 für die Qualität.
    3. Nenne konkrete Probleme als eine Aufzählung mit Spiegelstrichen.
    4. Gib eine kurze Zusammenfassung von maximal 3 Sätzen.

    Gib die Antwort NUR in diesem Format aus, ohne jeglichen Einleitungstext oder Markdown-Formatierung wie ```:
    Score: <int>
    Probleme:
    - <Problem 1>
    - <Problem 2>
    Zusammenfassung: <String>
    """

    try:
        # Initialisiere das Modell (Flash ist schnell und kosteneffizient)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        
        # Sende die Anfrage an die API
        response = model.generate_content(prompt)
        reply = response.text

        # Robuste Extraktion der Daten aus der Antwort mit Regex
        pattern = re.compile(
            r"Score:\s*(\d+)\s*Probleme:\s*(.*?)\s*Zusammenfassung:\s*(.*)",
            re.DOTALL | re.IGNORECASE
        )
        match = pattern.search(reply)

        if not match:
            raise ValueError("Could not parse the model's response format.")

        score = int(match.group(1).strip())
        
        # Extrahiere und bereinige den 'issues'-Block
        issues_text = match.group(2).strip()
        issues = [line.strip("- ") for line in issues_text.split('\n') if line.strip() and line.strip().startswith('-')]
        
        summary = match.group(3).strip()

        return AnalysisResult(score=score, issues=issues, summary=summary)

    except (ValueError, AttributeError) as e:
        # Dieser Block fängt Fehler ab, die beim Parsen der Antwort auftreten
        print(f"Fehler beim Parsen der Gemini-Antwort: {e}\nAntwort war:\n{reply}")
        return AnalysisResult(
            score=0, 
            issues=["Antwort des KI-Modells konnte nicht verarbeitet werden.", "Format war unerwartet."], 
            summary="Keine Zusammenfassung möglich."
        )
    except Exception as e:
        # Fängt alle anderen Fehler ab (z.B. API-Verbindungsprobleme)
        print(f"Ein unerwarteter Fehler mit der Gemini API ist aufgetreten: {e}")
        raise e
