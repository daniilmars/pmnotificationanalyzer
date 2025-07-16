import os
import re
import google.generativeai as genai
from app.models import AnalysisCase, AnalysisResult

def analyze_text(case: AnalysisCase) -> AnalysisResult:
    """
    Analysiert einen vollständigen Instandhaltungsfall mit der Google Gemini API.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GOOGLE_API_KEY environment variable is not set.")
    genai.configure(api_key=api_key)

    # Daten aus dem gesamten Fall für den Prompt zusammenstellen
    full_text_for_prompt = f"Meldungstext: {case.Notification.LongText}\n\n"
    
    # --- FINALE KORREKTUR: Korrekter Zugriff auf das Order-Dictionary ---
    if case.Order:
        # Wir greifen auf die Daten mit ['key'] zu, nicht mit .key
        full_text_for_prompt += f"Geplante Vorgänge im Auftrag: {case.Order.get('Operations', '')}\n"
        full_text_for_prompt += f"Geplante Komponenten: {case.Order.get('Components', '')}\n\n"
    # --------------------------------------------------------------------
        
    full_text_for_prompt += f"Durchgeführte Tätigkeiten (Rückmeldung): {case.Confirmation.Activities}"
    
    if case.ExternalProtocol:
        full_text_for_prompt += f"\n\nExternes Protokoll: {case.ExternalProtocol}"

    prompt = f"""
    Du bist ein GMP-Auditor. Analysiere den folgenden Instandhaltungsprozess auf Konsistenz und Vollständigkeit.
    Prüfe, ob die durchgeführten Tätigkeiten (inkl. externem Protokoll, falls vorhanden) zur Meldung und zum Auftrag passen.
    
    PROZESSDATEN:
    ---
    {full_text_for_prompt}
    ---

    BEWERTUNG:
    - Wurde das Problem aus der Meldung im Auftrag und in der Durchführung adressiert?
    - Passen die durchgeführten Tätigkeiten zu den geplanten Vorgängen?
    - Ist die gesamte Dokumentation GMP-konform (Ursache, Produkteinfluss, CAPA)?

    GIB DEINE ANTWORT NUR IN DIESEM EXAKTEN FORMAT ZURÜCK:
    Score: <int>
    Probleme:
    - <Liste der gefundenen Mängel>
    Zusammenfassung: <Zusammenfassung der Prozessqualität>
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(temperature=0.1))
        reply = response.text

        pattern = re.compile(r"Score:\s*(\d+)\s*Probleme:\s*(.*?)\s*Zusammenfassung:\s*(.*)", re.DOTALL | re.IGNORECASE)
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
