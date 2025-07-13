import os
import re
import google.generativeai as genai
from app.models import AnalysisResult

def analyze_text(text: str) -> AnalysisResult:
    """
    Analysiert einen SAP-Instandhaltungstext mit Google Gemini und extrahiert strukturierte Daten.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GOOGLE_API_KEY environment variable is not set or could not be loaded.")
    genai.configure(api_key=api_key)

    # Der Prompt wurde um die GMP-Kriterien erweitert
    prompt = f"""
    Du bist ein erfahrener GMP-Auditor und bewertest die Qualität von Instandhaltungsmeldungen in einem pharmazeutischen Produktionsbetrieb. Deine Bewertung muss extrem streng sein und sich an den Prinzipien von GMP und Datenintegrität (ALCOA+) orientieren.

    Bewertungsmatrix:
    - Score 90-100 (Audit-sicher): Alle 5 Säulen (GMP/ALCOA+, Rückverfolgbarkeit, Ursachenanalyse, Produkteinfluss, CAPA mit Vorbeugemassnahme) sind vollständig erfüllt. Alle IDs und Chargennummern sind vorhanden.
    - Score 70-89 (Gut, mit Lücken): Die Meldung ist grösstenteils konform, aber es fehlt eine explizite Vorbeugemassnahme oder die Ursachenanalyse ist nicht tiefgehend.
    - Score 40-69 (Mangelhaft): Es fehlt eine klare Bewertung des Produkteinflusses oder die Ursachenanalyse. Kritische IDs (z.B. Chargennummer) fehlen.
    - Score 10-39 (Schwerwiegend mangelhaft): Mehrere Säulen fehlen. Die Rückverfolgbarkeit ist nicht gegeben. Der Text ist unpräzise.
    - Score 0-9 (Ungenügend): Der Eintrag ist für ein GMP-Umfeld völlig unbrauchbar.

    Analysiere nun diesen Text:
    "{text}"

    Deine Analyse (im exakten Format):
    Score: <int>
    Probleme:
    - <Liste der konkreten GMP-Verstösse, z.B. "Fehlende Chargennummer verhindert Rückverfolgbarkeit", "Keine Bewertung des Produkteinflusses", "Keine Vorbeugemassnahme definiert">
    Zusammenfassung: <Kurze Zusammenfassung der GMP-Readiness des Eintrags>
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
            raise ValueError("Could not parse the model's response format.")

        score = int(match.group(1).strip())
        issues_text = match.group(2).strip()
        issues = [line.strip("- ") for line in issues_text.split('\n') if line.strip() and line.strip().startswith('-')]
        summary = match.group(3).strip()

        return AnalysisResult(score=score, issues=issues, summary=summary)

    except (ValueError, AttributeError) as e:
        print(f"Fehler beim Parsen der Gemini-Antwort: {e}\nAntwort war:\n{reply}")
        return AnalysisResult(
            score=0, 
            issues=["Antwort des KI-Modells konnte nicht verarbeitet werden.", "Format war unerwartet."], 
            summary="Keine Zusammenfassung möglich."
        )
    except Exception as e:
        print(f"Ein unerwarteter Fehler mit der Gemini API ist aufgetreten: {e}")
        raise e