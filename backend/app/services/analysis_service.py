import os
import re
import google.generativeai as genai
from app.models import AnalysisResponse, Problem, SuggestionResponse
from app.config_manager import get_config

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
        raise ValueError(f"Could not parse the response from the AI. Response was: {reply}")

    score = int(match.group(1).strip())
    issues_text = match.group(2).strip()
    summary = match.group(3).strip()

    # Create structured Problem objects
    problems = []
    raw_issues = [line.strip("- ") for line in issues_text.split('\n') if line.strip() and line.strip().startswith('-')]
    for issue_str in raw_issues:
        # This is a simple heuristic to assign field IDs. A more robust solution
        # might involve another LLM call or more complex NLP.
        field_id = "longTextDisplay" # Default
        has_suggestion = False
        if "long text" in issue_str.lower() or "description" in issue_str.lower():
            field_id = "longTextDisplay"
            has_suggestion = True
        elif "damage code" in issue_str.lower():
            field_id = "damageCodeDisplay"
        elif "cause code" in issue_str.lower():
            field_id = "causeCodeDisplay"
        
        problems.append(Problem(
            title=issue_str.split(':')[0] if ':' in issue_str else "Identified Issue",
            description=issue_str.split(':')[1].strip() if ':' in issue_str else issue_str,
            fieldId=field_id,
            hasSuggestion=has_suggestion
        ))

    return AnalysisResponse(score=score, problems=problems, summary=summary)


def analyze_text(notification_data: dict, language: str = "en") -> AnalysisResponse:
    """
    Analyzes an SAP maintenance notification using the Google Gemini API, 
    considering both long text and structured data.
    """
    config = get_config()
    llm_settings = config.get('analysis_llm_settings', {})
    quality_rules = config.get('quality_rules', [])

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GOOGLE_API_KEY environment variable is not set.")
    genai.configure(api_key=api_key)

    lang_map = { "en": "English", "de": "German" }
    output_language = lang_map.get(language, "English")

    # --- Build a detailed string from the structured data ---
    details = []
    details.append(f"- Priority: {notification_data.get('PriorityText', 'N/A')} (Code: {notification_data.get('Priority', 'N/A')})")
    details.append(f"- Description: {notification_data.get('Description', 'N/A')}")
    
    damage = notification_data.get('Damage', {})
    if damage and damage.get('Text'):
        details.append(f"- Damage: {damage.get('Text')} (Group: {damage.get('CodeGroup', 'N/A')}, Code: {damage.get('Code', 'N/A')})")

    cause = notification_data.get('Cause', {})
    if cause and cause.get('Text'):
        details.append(f"- Cause: {cause.get('Text')} (Group: {cause.get('CodeGroup', 'N/A')}, Code: {cause.get('Code', 'N/A')})")

    work_order = notification_data.get('WorkOrder')
    if work_order and work_order.get('Description'):
        details.append(f"- Linked Work Order: {work_order.get('Description')}")
    else:
        details.append("- Linked Work Order: None")

    structured_data_str = "\n".join(details)
    long_text = notification_data.get('LongText', '')
    rules_str = "\n".join([f"- {rule}" for rule in quality_rules])

    # --- Enhanced Prompt ---
    prompt = f"""
    You are a meticulous GMP (Good Manufacturing Practices) auditor evaluating the quality of a maintenance notification from a pharmaceutical plant. Your assessment must be extremely strict, adhering to GMP and data integrity (ALCOA+) principles.

    **Your Task:**
    Analyze the provided Long Text in conjunction with the structured data. The final score must reflect a holistic view of the notification's quality, paying close attention to the mandatory quality rules.

    **Mandatory Quality Rules:**
    {rules_str}

    **Evaluation Matrix (5 Pillars):**
    1.  **GMP/ALCOA+ Compliance:** Is the record complete, consistent, enduring, and available? 
    2.  **Traceability:** Are all necessary details present to understand what happened? (e.g., equipment IDs, batch numbers if applicable, locations).
    3.  **Root Cause Analysis:** Does the text describe a plausible root cause, and does it align with the structured Cause code? A simple description of the failure is not enough.
    4.  **Product Impact Assessment:** Is the potential impact on product quality, safety, or sterility explicitly assessed? This is CRITICAL.
    5.  **Corrective/Preventive Actions (CAPA):** Are immediate corrections and, more importantly, long-term preventive measures described or proposed?

    **Scoring Rubric:**
    -   **90-100 (Audit-Proof):** All 5 pillars and all mandatory rules are fully met. The structured data and long text are perfectly consistent.
    -   **70-89 (Good, Minor Gaps):** Largely compliant, but might lack a deep root cause analysis or an explicit preventive action.
    -   **40-69 (Deficient):** Fails on a major pillar, a mandatory rule, or has a missing product impact assessment.
    -   **10-39 (Major Deficiency):** Fails on multiple pillars or mandatory rules. Traceability is compromised.
    -   **0-9 (Unacceptable):** The entry is useless for GMP purposes.

    **Analysis Data:**

    **Structured Data:**
    {structured_data_str}

    **Long Text to Analyze:**
    "{long_text}"

    **Your Response:**
    Provide your response ONLY in the following format and ONLY in {output_language}. Do not add any other explanations.
    Score: <integer score>
    Probleme:
    - <Problem Title>: <Problem Description>
    - <Problem Title>: <Problem Description>
    Zusammenfassung: <A brief, one-sentence summary of the overall quality.>
    """.strip()

    try:
        model = genai.GenerativeModel(llm_settings.get('model', 'gemini-1.5-flash-latest'))
        generation_config = genai.types.GenerationConfig(temperature=llm_settings.get('temperature', 0.2))

        response = model.generate_content(prompt, generation_config=generation_config)
        reply = response.text
        
        return _parse_gemini_response(reply)

    except Exception as e:
        print(f"An error occurred while communicating with the Google Gemini API: {e}")
        raise e

def generate_suggestion(notification_data: dict, problem: Problem, language: str = "en") -> SuggestionResponse:
    """
    Generates a specific suggestion to fix a given problem in a notification.
    """
    lang_map = { "en": "en", "de": "de" }
    output_language = lang_map.get(language, "en")

    suggestion_text = ""
    # Use the reliable fieldId for logic instead of the unpredictable title
    if problem.fieldId == "longTextDisplay":
        if output_language == "de":
            suggestion_text = (
                "Der Langtext sollte detaillierter sein. Bitte verwenden Sie die folgende Vorlage:\n\n"
                "**Problembeschreibung:** (Was genau ist passiert? Welche Symptome wurden beobachtet?)\n"
                "**Ort:** (Wo genau am Equipment/an der Anlage ist das Problem aufgetreten?)\n"
                "**Auswirkung auf das Produkt:** (Wurde die Produktqualität, -sicherheit oder -sterilität beeinflusst? Wenn nicht, warum nicht?)\n"
                "**Sofortmaßnahmen:** (Welche unmittelbaren Schritte wurden unternommen, um das Problem zu beheben oder die Anlage zu sichern?)"
            )
        else:
            suggestion_text = (
                "The long text should be more detailed. Please use the following template:\n\n"
                "**Problem Description:** (What exactly happened? What symptoms were observed?)\n"
                "**Location:** (Where exactly on the equipment/facility did the problem occur?)\n"
                "**Product Impact:** (Was product quality, safety, or sterility affected? If not, why not?)\n"
                "**Immediate Actions:** (What immediate steps were taken to correct the issue or secure the equipment?)"
            )
    else:
        if output_language == "de":
            suggestion_text = "Für dieses spezifische Problem ist keine automatische Verbesserung verfügbar. Bitte überprüfen Sie die GMP-Richtlinien."
        else:
            suggestion_text = "No automatic improvement is available for this specific problem. Please review GMP guidelines."

    return SuggestionResponse(suggestion=suggestion_text)


def chat_with_assistant(notification_data: dict, question: str, analysis_context: AnalysisResponse, history: list, language: str = "en") -> dict:
    """
    Answers a user's question based on the context of a notification, its analysis, and the recent conversation history.
    """
    config = get_config()
    llm_settings = config.get('chat_llm_settings', {})

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GOOGLE_API_KEY environment variable is not set.")
    genai.configure(api_key=api_key)

    lang_map = { "en": "English", "de": "German" }
    output_language = lang_map.get(language, "English")

    # --- Build conversation history string ---
    history_str = ""
    for message in history:
        if message.get('role') == 'user':
            history_str += f"User: {message.get('content')}\n"
        else:
            history_str += f"Assistant: {message.get('content')}\n"

    # --- Build a detailed string from the structured data for context ---
    details = []
    details.append(f"- Notification ID: {notification_data.get('NotificationId', 'N/A')}")
    details.append(f"- Description: {notification_data.get('Description', 'N/A')}")
    details.append(f"- Priority: {notification_data.get('PriorityText', 'N/A')} (Code: {notification_data.get('Priority', 'N/A')})")
    
    context_str = "\n".join(details)
    long_text = notification_data.get('LongText', '')
    analysis_problems_str = "\n".join([f"- {p.title}: {p.description}" for p in analysis_context.problems])

    prompt = f"""
    You are an expert GMP (Good Manufacturing Practices) Quality Assistant for SAP Plant Maintenance.
    Your task is to act as a documentation coach. You must answer the user's question based *only* on the provided context.
    Your tone should be helpful, professional, and supportive.
    If the answer is not in the context, state that clearly. Do not invent information.

    **Formatting Rules:**
    - Use simple Markdown for formatting.
    - Use **bold text** for emphasis.
    - Use `*` for bullet points.

    --- START OF CONTEXT DATA ---

    **1. Raw Notification Data:**
    {context_str}

    **2. Long Text:**
    {long_text}

    **3. Current Quality Analysis:**
    - Quality Score: {analysis_context.score}/100
    - Identified Problems:
    {analysis_problems_str}
    - Summary: {analysis_context.summary}

    --- END OF CONTEXT DATA ---

    --- CONVERSATION HISTORY ---
    {history_str}
    --- END OF HISTORY ---

    Based on all the information above, answer the following question concisely and helpfully in {output_language}.

    **User's Question:** "{question}"
    """

    try:
        model = genai.GenerativeModel(llm_settings.get('model', 'gemini-1.5-flash-latest'))
        generation_config = genai.types.GenerationConfig(temperature=llm_settings.get('temperature', 0.4))
        response = model.generate_content(prompt, generation_config=generation_config)
        
        return {"answer": response.text.strip()}

    except Exception as e:
        print(f"An error occurred while communicating with the Google Gemini API: {e}")
        raise e
