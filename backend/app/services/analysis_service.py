import os
import json
import re
import time
import google.generativeai as genai
from app.models import AnalysisResponse
from app.config_manager import get_config

def _parse_gemini_response(reply: str) -> AnalysisResponse:
    """
    Parses the response from Gemini. Tries to parse as JSON first.
    If that fails, it attempts to extract JSON from code blocks.
    """
    try:
        # Attempt 1: Direct JSON parse
        data = json.loads(reply)
        return AnalysisResponse(**data)
    except json.JSONDecodeError:
        # Attempt 2: Extract from ```json ... ``` block
        match = re.search(r"```json\s*(.*?)\s*```", reply, re.DOTALL)
        if match:
            try:
                json_str = match.group(1)
                data = json.loads(json_str)
                return AnalysisResponse(**data)
            except json.JSONDecodeError:
                pass
        
        print(f"Warning: Could not parse JSON. Raw response: {reply}")
        raise ValueError("Failed to parse AI response as JSON.")

def analyze_text(notification_data: dict, language: str = "en") -> AnalysisResponse:
    """
    Analyzes an SAP maintenance notification using the Google Gemini API, 
    considering both long text and structured data. Retries on JSON errors.
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
    5.  **Corrective/Preventive Actions (CAPA):** Are immediate corrections, and more importantly, long-term preventive measures described or proposed?

    **Scoring Rubric:**
    -   **90-100 (Audit-Proof):** All 5 pillars and all mandatory rules are fully met.
    -   **70-89 (Good, Minor Gaps):** Largely compliant, but might lack a deep root cause analysis.
    -   **40-69 (Deficient):** Fails on a major pillar or mandatory rule.
    -   **10-39 (Major Deficiency):** Fails on multiple pillars.
    -   **0-9 (Unacceptable):** Useless for GMP purposes.

    **Analysis Data:**
    
    **Structured Data:**
    {structured_data_str}

    **Long Text to Analyze:**
    "{long_text}"

    **Response Format:**
    Provide your response **ONLY** as a valid JSON object (no markdown, no prose outside JSON) with the following structure. ensuring all content is in {output_language}:

    {{
      "score": <integer between 0 and 100>,
      "summary": "<string: A concise executive summary of the quality>",
      "problems": [
        {{
          "field": "<one of: DESCRIPTION, LONG_TEXT, DAMAGE_CODE, CAUSE_CODE, WORK_ORDER_DESCRIPTION, GENERAL>",
          "severity": "<one of: Critical, Major, Minor>",
          "description": "<string: Specific description of the issue>"
        }}
      ]
    }}
    """.strip()

    max_retries = 3
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel(
                llm_settings.get('model', 'gemini-2.5-flash'),
                safety_settings={'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
                                 'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
                                 'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
                                 'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE'},
                 generation_config={"response_mime_type": "application/json"}
            )
            generation_config = genai.types.GenerationConfig(
                temperature=llm_settings.get('temperature', 0.2),
                response_mime_type="application/json"
            )

            response = model.generate_content(prompt, generation_config=generation_config)
            reply = response.text
            
            return _parse_gemini_response(reply)

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                print(f"An error occurred while communicating with the Google Gemini API after {max_retries} attempts.")
                raise e
            time.sleep(1) # Wait a bit before retrying

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
    analysis_problems_str = "\n".join([f"- {p.description}" for p in analysis_context.problems])

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
    """.strip()

    try:
        model = genai.GenerativeModel(
            llm_settings.get('model', 'gemini-2.5-flash'),
            safety_settings={'HARM_CATEGORY_HARASSMENT': 'BLOCK_NONE',
                             'HARM_CATEGORY_HATE_SPEECH': 'BLOCK_NONE',
                             'HARM_CATEGORY_SEXUALLY_EXPLICIT': 'BLOCK_NONE',
                             'HARM_CATEGORY_DANGEROUS_CONTENT': 'BLOCK_NONE'}
        )
        generation_config = genai.types.GenerationConfig(temperature=llm_settings.get('temperature', 0.4))
        response = model.generate_content(prompt, generation_config=generation_config)
        
        return {"answer": response.text.strip()}

    except Exception as e:
        print(f"An error occurred while communicating with the Google Gemini API: {e}")
        raise e