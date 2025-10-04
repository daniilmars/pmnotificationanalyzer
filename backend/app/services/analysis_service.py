import os
import re
import google.generativeai as genai
from app.models import AnalysisResponse
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
    issues = [line.strip("- ") for line in issues_text.split('\n') if line.strip() and line.strip().startswith('-')]
    summary = match.group(3).strip()

    return AnalysisResponse(score=score, problems=issues, summary=summary)


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
    - <Problem 1: Be specific, e.g., "Product impact was not assessed.">
    - <Problem 2: e.g., "Root cause is missing, only the symptom is described.">
    - <Problem 3: e.g., "Inconsistency: The long text mentions a 'leak' but the damage code is 'vibration'.">
    Zusammenfassung: <A brief, one-sentence summary of the overall quality.>
    """.strip()

    try:
        model = genai.GenerativeModel(llm_settings.get('model', 'gemini-2.5-flash'))
        generation_config = genai.types.GenerationConfig(temperature=llm_settings.get('temperature', 0.2))

        response = model.generate_content(prompt, generation_config=generation_config)
        reply = response.text
        
        return _parse_gemini_response(reply)

    except Exception as e:
        print(f"An error occurred while communicating with the Google Gemini API: {e}")
        raise e



def chat_with_assistant(notification_data: dict, question: str, analysis_context: AnalysisResponse, language: str = "en") -> dict:
    """
    Answers a user's question based on the context of an SAP maintenance notification and its quality analysis.
    """
    config = get_config()
    llm_settings = config.get('chat_llm_settings', {})

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("CRITICAL: GOOGLE_API_KEY environment variable is not set.")
    genai.configure(api_key=api_key)

    lang_map = { "en": "English", "de": "German" }
    output_language = lang_map.get(language, "English")

    # --- Build a detailed string from the structured data for context ---
    details = []
    details.append(f"- Notification ID: {notification_data.get('NotificationId', 'N/A')}")
    details.append(f"- Description: {notification_data.get('Description', 'N/A')}")
    details.append(f"- Priority: {notification_data.get('PriorityText', 'N/A')} (Code: {notification_data.get('Priority', 'N/A')})")
    details.append(f"- Created By: {notification_data.get('CreatedByUser', 'N/A')} on {notification_data.get('CreationDate', 'N/A')}")
    details.append(f"- Status: {notification_data.get('SystemStatus', 'N/A')}")
    
    damage = notification_data.get('Damage', {})
    if damage and damage.get('Text'):
        details.append(f"- Damage: {damage.get('Text')} (Group: {damage.get('CodeGroup', 'N/A')}, Code: {damage.get('Code', 'N/A')})")

    cause = notification_data.get('Cause', {})
    if cause and cause.get('Text'):
        details.append(f"- Cause: {cause.get('Text')} (Group: {cause.get('CodeGroup', 'N/A')}, Code: {cause.get('Code', 'N/A')})")

    work_order = notification_data.get('WorkOrder')
    if work_order:
        details.append(f"- Linked Work Order: {work_order.get('OrderId')} - {work_order.get('Description')}")
        details.append(f"  - Order Status: {work_order.get('SystemStatus')}")
        if work_order.get('Operations'):
            details.append("  - Operations:")
            for op in work_order['Operations']:
                details.append(f"    - {op.get('OperationNumber')}: {op.get('Description')}")
    else:
        details.append("- Linked Work Order: None")

    context_str = "\n".join(details)
    long_text = notification_data.get('LongText', '')
    analysis_problems_str = "\n".join([f"- {p}" for p in analysis_context.problems])

    prompt = f"""
    You are an expert GMP (Good Manufacturing Practices) Quality Assistant for SAP Plant Maintenance.
    Your task is to act as a documentation coach. You must answer the user's question based *only* on the provided context, which includes both the raw data of a maintenance notification and its recent quality analysis.
    Your tone should be helpful, professional, and supportive.
    If the answer is not in the context, state that clearly. Do not invent information.

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

    Based on all the information above, answer the following question concisely and helpfully in {output_language}.

    **User's Question:** "{question}"
    """

    try:
        model = genai.GenerativeModel(llm_settings.get('model', 'gemini-2.5-flash'))
        generation_config = genai.types.GenerationConfig(temperature=llm_settings.get('temperature', 0.4))
        response = model.generate_content(prompt, generation_config=generation_config)
        
        return {"answer": response.text.strip()}

    except Exception as e:
        print(f"An error occurred while communicating with the Google Gemini API: {e}")
        raise e


